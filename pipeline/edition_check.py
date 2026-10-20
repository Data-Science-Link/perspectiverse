"""Free per-edition planet check. No network and no model calls.

This is a detector. It reads a published snapshot and writes a report. It does
not hide, rewrite, or drop planets, and it does not change the snapshot.

Each failure names the pipeline stage that should have prevented it, so the
fix is upstream (Michael, 2026-10-20): ingest, clustering/attach, faces/stance,
or labeling. A later cleanup pass is not the fix.

The post floor is ``min_planet_posts`` from settings. #266 raises that setting
to 30; until it merges, planets under 30 are listed as a revisit, not dropped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.chitchat_guard import PLEASANTRY_SHARE_DROP, planet_chitchat_reason
from pipeline.cluster_math import STOPWORDS
from pipeline.label import FALLBACK_TITLE, content_tokens, subject_stem, titles_alike
from pipeline.label_guard import PENDING_TITLE, reader_label_issue
from pipeline.language import edition_filter_reason
from pipeline.schema import ALLOWED_CATEGORIES
from pipeline.duplicate_rate import duplicate_rates, render_duplicate_lines
from pipeline.settings import load_settings
from pipeline.spam_guard import guard_reason

# A title fits when at least half of its content words show up in the posts.
TITLE_OVERLAP_FLOOR = 0.5
_TOKEN = re.compile(r"[A-Za-z0-9]+")
_EXTRA_STOP = frozenset(
    {
        "versus",
        "vs",
        "into",
        "over",
        "under",
        "about",
        "from",
        "with",
        "this",
        "that",
        "these",
        "those",
        "than",
        "then",
        "them",
        "they",
        "their",
        "there",
        "here",
        "have",
        "has",
        "been",
        "were",
        "will",
        "would",
        "could",
        "should",
        "your",
        "just",
        "only",
        "also",
        "more",
        "most",
        "some",
        "such",
        "what",
        "when",
        "where",
        "which",
        "while",
        "because",
        "after",
        "before",
    }
)

CHECK_ORDER = (
    "title_fit",
    "faces_different",
    "junk",
    "label",
    "post_floor",
)
# Where an upstream fix belongs. The check does not apply that fix.
STAGE_FOR_CHECK = {
    "title_fit": "labeling",
    "faces_different": "faces/stance",
    "junk": "ingest",
    "label": "labeling",
    "post_floor": "clustering/attach",
}
THIN_SECTION_STAGE = "clustering/attach"
# #266's floor. Reported when settings still say less, so those planets are
# visible. They stay in the edition until the setting itself changes.
SHADOW_POST_FLOOR = 30
_DOTTED_ACRONYM = re.compile(r"\b(?:[A-Za-z]\.){2,}")


def _settings_value(settings: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(settings.get(key, default))
    except (TypeError, ValueError):
        return default


def _raw_tokens(text: str) -> list[str]:
    return _TOKEN.findall(text or "")


def _collapse_dotted_acronyms(text: str) -> str:
    """Turn U.S. and A.D.H.D. into US and ADHD before the word overlap."""
    return _DOTTED_ACRONYM.sub(lambda match: match.group(0).replace(".", ""), text or "")


def _title_for_overlap(title: str) -> str:
    """Ignore a trailing disambiguation number from ``unique_label`` (" 2")."""
    return re.sub(r"\s+\d+$", "", _collapse_dotted_acronyms(title).strip())


def content_words(text: str) -> set[str]:
    """Content words for the free title-overlap signal.

    Long words use the same cutoff as ``content_tokens``. A short token is
    kept when the title wrote it as an acronym or it contains a digit, so
    "US" and "PS5" still have to show up in the posts.
    """
    kept = set(content_tokens(text))
    for token in _raw_tokens(text):
        lowered = token.lower()
        if lowered in STOPWORDS or lowered in _EXTRA_STOP:
            continue
        if lowered in kept:
            continue
        if any(char.isdigit() for char in lowered) or (token.isupper() and len(lowered) >= 2):
            kept.add(lowered)
    return kept


def _stem(word: str) -> str:
    if len(word) >= 4:
        return subject_stem(word)
    return word


def words_overlap(title_words: set[str], post_words: set[str]) -> set[str]:
    """Title words that appear in the posts, including a shared stem."""
    post_stems = {_stem(word) for word in post_words}
    hits: set[str] = set()
    for word in title_words:
        stem = _stem(word)
        if word in post_words or stem in post_stems:
            hits.add(word)
            continue
        if len(stem) >= 4 and any(
            other.startswith(stem) or stem.startswith(other)
            for other in post_stems
            if len(other) >= 4
        ):
            hits.add(word)
    return hits


def title_overlap(title: str, posts_text: str) -> tuple[float, set[str], set[str]]:
    title_words = content_words(title)
    post_words = content_words(posts_text)
    if not title_words:
        return 0.0, title_words, set()
    hits = words_overlap(title_words, post_words)
    return len(hits) / len(title_words), title_words, hits


def title_fits(title: str, posts_text: str) -> tuple[bool, str]:
    """True when the title's content words overlap the posts."""
    ratio, title_words, hits = title_overlap(
        _title_for_overlap(title),
        _collapse_dotted_acronyms(posts_text),
    )
    if not title_words:
        return False, "title has no content words"
    if ratio + 1e-12 >= TITLE_OVERLAP_FLOOR:
        return True, f"{ratio:.0%} of title words appear in the posts"
    missing = sorted(title_words - hits)
    return False, f"{ratio:.0%} overlap; missing {', '.join(missing)}"


def _face_posts(face: dict) -> list[dict]:
    posts: list[dict] = []
    for rep in face.get("representative_posts") or []:
        if isinstance(rep, dict) and str(rep.get("text") or "").strip():
            posts.append({"text": rep.get("text"), "clean_text": rep.get("text")})
    return posts


def _planet_posts(planet: dict) -> list[dict]:
    posts: list[dict] = []
    for face in planet.get("perspectives") or []:
        if isinstance(face, dict):
            posts.extend(_face_posts(face))
    return posts


def _posts_text(posts: list[dict]) -> str:
    return "\n".join(str(post.get("text") or "") for post in posts)


def _stance_fold():
    """#268's local fold, once that branch is on main. None until then."""
    try:
        from pipeline import stance
    except ImportError:
        return None
    return getattr(stance, "local_faces_fold", None)


def check_title_fit(planet: dict) -> list[str]:
    posts = _planet_posts(planet)
    if not posts:
        return ["no representative posts to compare with the title"]
    reasons: list[str] = []
    name = str(planet.get("name") or "")
    ok, detail = title_fits(name, _posts_text(posts))
    if not ok:
        reasons.append(f"planet title {name!r}: {detail}")
    for face in planet.get("perspectives") or []:
        if not isinstance(face, dict):
            continue
        title = str(face.get("title") or "")
        face_posts = _face_posts(face) or posts
        ok, detail = title_fits(title, _posts_text(face_posts))
        if not ok:
            reasons.append(f"face title {title!r}: {detail}")
    return reasons


def check_faces_different(planet: dict) -> list[str]:
    """Alike titles, or #268's fold when that function is on this tree.

    One face is a pass. A single view is allowed.
    """
    faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
    if len(faces) < 2:
        return []
    fold = _stance_fold()
    reasons: list[str] = []
    for index, left in enumerate(faces):
        for right in faces[index + 1 :]:
            left_title = str(left.get("title") or "")
            right_title = str(right.get("title") or "")
            if fold is not None:
                try:
                    same = bool(
                        fold(left, right, _face_posts(left), _face_posts(right))
                    )
                except (TypeError, ValueError, KeyError):
                    same = False
                if same:
                    reasons.append(
                        f"stance gate: {left_title!r} and {right_title!r} "
                        "share a subject and do not disagree"
                    )
                    continue
            if titles_alike(left_title, right_title):
                reasons.append(f"alike titles: {left_title!r} and {right_title!r}")
    return reasons


def check_junk(planet: dict) -> list[str]:
    """Chit-chat planet guard, plus link-only, non-English, and spam posts.

    The chit-chat decision is ``planet_chitchat_reason`` (#208 / #264's
    planet guard on this tree). Link-only and language use
    ``edition_filter_reason``. Spam uses ``guard_reason``. A planet fails
    the second group only when those posts are at least the chit-chat
    share (55%).
    """
    posts = _planet_posts(planet)
    if not posts:
        return []
    chit = planet_chitchat_reason(posts, [])
    if chit:
        return [chit]
    blocked = 0
    for post in posts:
        if edition_filter_reason(post):
            blocked += 1
            continue
        reason = guard_reason(post)
        if reason and reason != "empty":
            blocked += 1
    share = blocked / len(posts)
    if share >= PLEASANTRY_SHARE_DROP:
        return [f"{share:.0%} of the shown posts are link-only, non-English, or spam"]
    return []


def _label_missing(title: str) -> bool:
    text = " ".join(str(title or "").split())
    if not text:
        return True
    lowered = text.lower()
    if lowered == PENDING_TITLE.lower() or lowered == FALLBACK_TITLE.lower():
        return True
    if lowered in {"untitled", "untitled topic", "mixed remarks"}:
        return True
    return False


def check_label(planet: dict) -> list[str]:
    """A category and a reader title, and the #265 label guard."""
    reasons: list[str] = []
    name = str(planet.get("name") or "")
    if _label_missing(name):
        reasons.append("planet label missing")
    category = str(planet.get("category") or "").strip()
    if category not in ALLOWED_CATEGORIES:
        reasons.append("section label missing" if not category else f"section label {category!r} is not a known section")
    posts = _planet_posts(planet)
    terms: list[str] = []
    for face in planet.get("perspectives") or []:
        if isinstance(face, dict):
            terms.extend(str(term) for term in (face.get("top_terms") or []) if str(term).strip())
    issue = reader_label_issue(
        name,
        str(planet.get("summary") or ""),
        planet_name=name,
        terms=terms,
        posts=posts,
        kind="planet",
    )
    if issue:
        reasons.append(f"planet label: {issue}")
    for face in planet.get("perspectives") or []:
        if not isinstance(face, dict):
            continue
        title = str(face.get("title") or "")
        if _label_missing(title):
            reasons.append("face label missing")
            continue
        face_terms = [str(term) for term in (face.get("top_terms") or []) if str(term).strip()] or terms
        face_issue = reader_label_issue(
            title,
            str(face.get("summary") or ""),
            planet_name=name,
            terms=face_terms,
            posts=_face_posts(face) or posts,
            kind="face",
        )
        if face_issue:
            reasons.append(f"face {title!r}: {face_issue}")
    return reasons


def planet_post_count(planet: dict) -> int:
    raw = planet.get("post_count")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    total = 0
    for face in planet.get("perspectives") or []:
        if isinstance(face, dict):
            try:
                total += int(face.get("post_count") or 0)
            except (TypeError, ValueError):
                continue
    return total


def check_post_floor(planet: dict, floor: int) -> list[str]:
    """``min_planet_posts``. Zero disables the floor, matching settings."""
    if floor <= 0:
        return []
    count = planet_post_count(planet)
    if count < floor:
        return [f"{count} posts is under the {floor}-post floor"]
    return []


def iter_published(payload: dict) -> list[tuple[str, dict]]:
    """Catalog planets, then each section planet. A reader can open both."""
    rows: list[tuple[str, dict]] = []
    for topic in payload.get("topics") or []:
        if isinstance(topic, dict):
            rows.append(("catalog", topic))
    sections = payload.get("sections") or {}
    if isinstance(sections, dict):
        for section, planets in sections.items():
            if not isinstance(planets, list):
                continue
            for planet in planets:
                if isinstance(planet, dict):
                    rows.append((str(section), planet))
    return rows


def check_planet(planet: dict, *, floor: int) -> dict[str, list[str]]:
    return {
        "title_fit": check_title_fit(planet),
        "faces_different": check_faces_different(planet),
        "junk": check_junk(planet),
        "label": check_label(planet),
        "post_floor": check_post_floor(planet, floor),
    }


def thin_sections(payload: dict, *, floor: int, catalog_size: int) -> list[dict[str, Any]]:
    """Sections that cannot fill a solar system, now or after the post floor.

    This is the #266 revisit: the edition looks thin on a low-volume day, or
    real stories sit under the floor and the section would open with holes.
    """
    sections = payload.get("sections") or {}
    if not isinstance(sections, dict):
        return []
    flagged: list[dict[str, Any]] = []
    target = catalog_size if catalog_size > 0 else 0
    for section, planets in sections.items():
        if not isinstance(planets, list):
            continue
        counts = [planet_post_count(planet) for planet in planets if isinstance(planet, dict)]
        clearing = [count for count in counts if floor <= 0 or count >= floor]
        reasons: list[str] = []
        if target and len(counts) < target:
            reasons.append(f"{len(counts)} published planets, solar system holds {target}")
        if target and floor > 0 and len(clearing) < target:
            reasons.append(
                f"{len(clearing)} planets clear the {floor}-post floor, solar system holds {target}"
            )
        if not reasons:
            continue
        # One flag per section. The floor line repeats the published-count line
        # when every planet already clears the floor and the section is short.
        if len(reasons) == 2 and len(counts) == len(clearing):
            reasons = [reasons[0]]
        flagged.append(
            {
                "section": str(section),
                "stage": THIN_SECTION_STAGE,
                "planets": len(counts),
                "clearing_floor": len(clearing),
                "detail": "; ".join(reasons),
            }
        )
    return flagged


def floor_revisit(payload: dict, *, floor: int, catalog_size: int) -> dict[str, Any] | None:
    """Planets under #266's 30-post floor while settings still use a lower one.

    Not a failure and not a drop. The stage is clustering/attach, which is
    where the floor is supposed to keep them out of the edition.
    """
    if floor <= 0 or floor >= SHADOW_POST_FLOOR:
        return None
    under: list[dict[str, Any]] = []
    for scope, planet in iter_published(payload):
        count = planet_post_count(planet)
        if count >= SHADOW_POST_FLOOR:
            continue
        under.append(
            {
                "scope": scope,
                "id": planet.get("id"),
                "name": str(planet.get("name") or ""),
                "post_count": count,
                "stage": STAGE_FOR_CHECK["post_floor"],
            }
        )
    shadow_settings_floor = SHADOW_POST_FLOOR
    thin = thin_sections(payload, floor=shadow_settings_floor, catalog_size=catalog_size)
    return {
        "shadow_floor": SHADOW_POST_FLOOR,
        "stage": STAGE_FOR_CHECK["post_floor"],
        "note": (
            f"min_planet_posts is {floor}, so these are not failures and this check "
            f"does not drop them. #266 sets the floor to {SHADOW_POST_FLOOR} in "
            "clustering/attach."
        ),
        "planets_under_shadow_floor": len(under),
        "planets": under,
        "thin_sections_at_shadow_floor": thin,
    }


def _stance_signal() -> str:
    if _stance_fold() is not None:
        return "local_faces_fold+titles_alike"
    return "titles_alike"


def check_edition(
    payload: dict,
    settings: dict[str, Any] | None = None,
    *,
    source: str | None = None,
    source_commit: str | None = None,
    previous: dict | None = None,
    labeled_path: Path | None = None,
) -> dict[str, Any]:
    """Check one published snapshot. Returns the report dict."""
    chosen = settings if settings is not None else load_settings()
    floor = _settings_value(chosen, "min_planet_posts", 0)
    catalog_size = _settings_value(chosen, "catalog_size", 10)
    failures: list[dict[str, Any]] = []
    by_check: Counter[str] = Counter()
    by_stage: Counter[str] = Counter()
    for scope, planet in iter_published(payload):
        found = check_planet(planet, floor=floor)
        fired = {name: reasons for name, reasons in found.items() if reasons}
        if not fired:
            continue
        stages: list[str] = []
        for name in CHECK_ORDER:
            if not found[name]:
                continue
            by_check[name] += 1
            stage = STAGE_FOR_CHECK[name]
            if stage not in stages:
                stages.append(stage)
                by_stage[stage] += 1
        failures.append(
            {
                "scope": scope,
                "id": planet.get("id"),
                "name": str(planet.get("name") or ""),
                "post_count": planet_post_count(planet),
                "stages": stages,
                "checks": [
                    {
                        "check": name,
                        "stage": STAGE_FOR_CHECK[name],
                        "detail": "; ".join(found[name]),
                    }
                    for name in CHECK_ORDER
                    if found[name]
                ],
            }
        )
    planets = len(iter_published(payload))
    failed = len(failures)
    passed = planets - failed
    rate = (passed / planets) if planets else 1.0
    flags = thin_sections(payload, floor=floor, catalog_size=catalog_size)
    return {
        "source": source,
        "source_commit": source_commit,
        "edition_date": payload.get("last_updated"),
        "min_planet_posts": floor,
        "catalog_size": catalog_size,
        "title_overlap_floor": TITLE_OVERLAP_FLOOR,
        "junk_share": PLEASANTRY_SHARE_DROP,
        "stance_signal": _stance_signal(),
        "planets": planets,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(rate, 4),
        "failure_counts": {name: by_check.get(name, 0) for name in CHECK_ORDER},
        "stage_counts": {stage: by_stage.get(stage, 0) for stage in (
            "ingest",
            "clustering/attach",
            "faces/stance",
            "labeling",
        )},
        "thin_sections": flags,
        "floor_revisit": floor_revisit(payload, floor=floor, catalog_size=catalog_size),
        "duplicate_rate": duplicate_rates(
            payload,
            previous=previous,
            labeled_path=labeled_path,
            floor=floor,
        ),
        "failures": failures,
        "detector_only": True,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Short summary. The JSON report has every failing planet."""
    rate = float(report.get("pass_rate") or 0.0)
    planets = int(report.get("planets") or 0)
    passed = int(report.get("passed") or 0)
    failed = int(report.get("failed") or 0)
    lines = [
        "# Edition self-check",
        "",
        f"Pass rate **{rate:.1%}** ({passed} of {planets} planets, {failed} failed).",
        "",
        f"- Edition date: {report.get('edition_date') or 'unknown'}",
        f"- Source: {report.get('source') or 'unknown'}",
        f"- Snapshot commit: {report.get('source_commit') or 'n/a'}",
        f"- Post floor (`min_planet_posts`): {report.get('min_planet_posts')}",
        f"- Face signal: {report.get('stance_signal')}",
        "- This check does not change the edition.",
        "",
    ]
    lines.extend(render_duplicate_lines(report))
    lines.extend([
        "## Where to fix",
        "",
    ])
    stages = report.get("stage_counts") or {}
    for stage in ("ingest", "clustering/attach", "faces/stance", "labeling"):
        lines.append(f"- {stage}: {int(stages.get(stage) or 0)} planets")
    lines.extend(["", "## Failures by check", ""])
    counts = report.get("failure_counts") or {}
    ranked = sorted(CHECK_ORDER, key=lambda name: (-int(counts.get(name) or 0), name))
    for name in ranked:
        lines.append(f"- {name}: {int(counts.get(name) or 0)} planets")
    lines.extend(["", "## Thin sections", ""])
    flags = report.get("thin_sections") or []
    if not flags:
        lines.append("None.")
    else:
        for flag in flags:
            lines.append(
                f"- {flag.get('section')} ({flag.get('stage')}): {flag.get('detail')}"
            )
    revisit = report.get("floor_revisit")
    if revisit:
        lines.extend(["", "## 30-post floor revisit (not a failure yet)", ""])
        lines.append(str(revisit.get("note") or ""))
        lines.append(
            f"- {revisit.get('planets_under_shadow_floor')} published planets have "
            f"fewer than {revisit.get('shadow_floor')} posts. Stage: {revisit.get('stage')}."
        )
        shadow_thin = revisit.get("thin_sections_at_shadow_floor") or []
        if shadow_thin:
            names = ", ".join(str(flag.get("section")) for flag in shadow_thin)
            lines.append(f"- Sections that would look thin at that floor: {names}.")
    lines.extend(["", "## Top failing planets", ""])
    failures = list(report.get("failures") or [])
    failures.sort(key=lambda row: (-len(row.get("checks") or []), str(row.get("scope")), str(row.get("name"))))
    if not failures:
        lines.append("None.")
    else:
        for row in failures[:15]:
            checks = ", ".join(
                f"{item.get('check')} → {item.get('stage')}" for item in row.get("checks") or []
            )
            lines.append(
                f"- {row.get('scope')} / {row.get('name')} "
                f"({row.get('post_count')} posts): {checks}"
            )
        if len(failures) > 15:
            lines.append(f"- … {len(failures) - 15} more in the JSON report")
    lines.append("")
    return "\n".join(lines)


def _print_github_warning(report: dict[str, Any]) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    rate = float(report.get("pass_rate") or 0.0)
    if rate >= 1.0 and not report.get("thin_sections"):
        return
    text = (
        f"Edition self-check pass rate {rate:.1%} "
        f"({report.get('failed')} of {report.get('planets')} planets failed, "
        f"{len(report.get('thin_sections') or [])} thin sections). "
        "Report only; this does not hold the snapshot."
    )
    print(f"::warning::{text}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Free per-edition planet self-check")
    parser.add_argument("data", nargs="?", default="public/data.json", help="Path to data.json")
    parser.add_argument("--json", dest="json_path", help="Write the JSON report here")
    parser.add_argument("--markdown", dest="markdown_path", help="Write the markdown summary here")
    parser.add_argument("--source-commit", help="Commit the snapshot was taken from, stored in the report")
    parser.add_argument("--previous", help="Yesterday's data.json, or a previous self-check JSON")
    parser.add_argument("--labeled", help="Labeled pair CSV. Defaults to docs/evidence/275/oct19-pairs.csv")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Exit 0 after writing the report. A failing edition does not fail the process.",
    )
    args = parser.parse_args(argv)
    path = Path(args.data)
    if not path.is_file():
        print(f"Edition self-check: no snapshot at {path}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Edition self-check: {path} is not JSON ({exc})", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print(f"Edition self-check: {path} is not an edition object", file=sys.stderr)
        return 2
    previous = None
    if args.previous:
        previous_path = Path(args.previous)
        if not previous_path.is_file():
            print(f"Edition self-check: no previous snapshot at {previous_path}", file=sys.stderr)
            return 2
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    labeled = Path(args.labeled) if args.labeled else None
    report = check_edition(
        payload,
        source=str(path),
        source_commit=args.source_commit,
        previous=previous,
        labeled_path=labeled,
    )
    rendered = render_markdown(report)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_path:
        Path(args.markdown_path).write_text(rendered, encoding="utf-8")
    print(
        f"EDITION_CHECK pass_rate={report['pass_rate']:.4f} "
        f"planets={report['planets']} failed={report['failed']} "
        f"thin_sections={len(report['thin_sections'])} "
        f"floor={report['min_planet_posts']} "
        f"dup_before={report['duplicate_rate']['before']['planets']['rate']:.4f} "
        f"dup_after={report['duplicate_rate']['after']['planets']['rate']:.4f}"
    )
    print(rendered)
    _print_github_warning(report)
    if args.report_only or report["failed"] == 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
