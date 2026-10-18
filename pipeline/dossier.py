"""Private 2–4 page briefings for planets and perspectives.

The daily pipeline keeps writing ``summary``, ``brief``, and ``detail`` into
``data.json``. Those three public tiers are produced from a longer internal
briefing plus the top posts. The briefing itself stays in Cloudflare R2 under
``dossiers/`` and is never copied into ``public/`` or ``data.json``.

The switch is off. ``dossiers: false`` and an unset ``PERSPECTIVERSE_DOSSIERS``
make no model call and no R2 write. Turning it on spends against the same
$1/day pipeline cap as labeling. A future visitor chat that reads these
objects pays for its own calls; this module does not meter a chat.

Rebuilds are the exception. A stored briefing is reused unless more than 20%
of the current post URIs are new, or a post newly enters the top 8 with more
likes than the least-liked post already in that top 8. A tie among equal
likes does not rebuild.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pipeline.briefs import sentences
from pipeline.r2 import assert_dossier_key, get_private_object, load_r2_config, put_private_object

# Same character-to-token rule as scripts/estimate_prompt_tokens.py.
CHARS_PER_TOKEN = Decimal("3.6")
# Llama 3.3 70B Turbo list price, the pipeline DeepInfra model.
# Same figures as scripts/measure_stance.py and the DeepInfra handoff note.
# Input / output, USD per 1,000,000 tokens.
LLAMA_70B_INPUT_USD_PER_MILLION = Decimal("0.10")
LLAMA_70B_OUTPUT_USD_PER_MILLION = Decimal("0.32")
# 450 words a page, 5 characters a word, then / 3.6.
# 900 words -> 1250 tokens. 1800 words -> 2500 tokens.
DOSSIER_WORDS_PER_PAGE = 450
DOSSIER_MIN_WORDS = 900
DOSSIER_MAX_WORDS = 1800
DOSSIER_OUTPUT_TOKENS_2PAGE = 1250
DOSSIER_OUTPUT_TOKENS_4PAGE = 2500
READER_OUTPUT_TOKENS = 500
# A model that overruns the 1,800-word ask. Used only as an approval ceiling.
OUTPUT_OVERSHOOT = Decimal("1.20")

DOSSIER_PROMPT_VERSION = "1"
SAMPLE_LIMIT = 40
TOP_N = 8
# Rebuild only when the share of current URIs missing from the stored set
# is strictly greater than this. Exactly 20% reuses.
NEW_POST_FRACTION = 0.20
# catalog_size 10, plus 10 newspaper sections. Planning count, not a cap change.
PLANNING_PLANETS = 110
# 220 perspectives / 110 planets on 2026-10-08. Planning face count.
PLANNING_FACES_PER_PLANET = 2
# Mean post length in the retained seed corpus (pipeline/data/live_corpus.db).
PLANNING_POST_CHARS = 191

HEADINGS = (
    "Subject",
    "Main arguments",
    "Evidence and sources cited",
    "Sub-camps",
    "What the other side says",
    "Notable quotes",
    "What changed this week",
)

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_ID = re.compile(r"[A-Za-z0-9]{1,32}\Z")
_URL = re.compile(r"https?://\S+")
_FENCE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


def dossiers_enabled(settings: dict | None = None) -> bool:
    """True only when the caller turned the switch on. Default is off."""
    if settings is not None:
        return bool(settings.get("dossiers"))
    raw = (os.getenv("PERSPECTIVERSE_DOSSIERS") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def estimate_tokens(text: str) -> int:
    """Integer tokens at 3.6 characters each, matching the repo's estimator."""
    return int(Decimal(len(text)) / CHARS_PER_TOKEN)


def price_tokens(input_tokens: int, output_tokens: int) -> Decimal:
    """USD at the Llama 3.3 70B Turbo rates stored in this repo."""
    cost = (
        Decimal(int(input_tokens)) * LLAMA_70B_INPUT_USD_PER_MILLION
        + Decimal(int(output_tokens)) * LLAMA_70B_OUTPUT_USD_PER_MILLION
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def post_uri(post: dict) -> str:
    uri = str(post.get("uri") or "").strip()
    if uri:
        return uri
    blob = f"{post.get('author')}\n{post.get('text')}".encode("utf-8")
    return "local:" + hashlib.sha256(blob).hexdigest()[:16]


def stable_slug(*parts: str) -> str:
    raw = "-".join(part for part in parts if str(part or "").strip())
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return (slug[:80] or "untitled")


def edition_markdown_key(edition: str, planet_id: object, perspective_id: object | None = None) -> str:
    if not _DATE.fullmatch(str(edition or "")):
        raise ValueError(f"edition must be YYYY-MM-DD, found {edition!r}")
    planet = str(planet_id or "")
    if not _ID.fullmatch(planet):
        raise ValueError(f"planet id is not a dossier key: {planet!r}")
    if perspective_id is None:
        key = f"dossiers/{edition}/{planet}.md"
    else:
        face = str(perspective_id)
        if not _ID.fullmatch(face):
            raise ValueError(f"perspective id is not a dossier key: {face!r}")
        key = f"dossiers/{edition}/{planet}/{face}.md"
    assert_dossier_key(key)
    return key


def edition_meta_key(edition: str, planet_id: object, perspective_id: object | None = None) -> str:
    markdown = edition_markdown_key(edition, planet_id, perspective_id)
    key = markdown[: -len(".md")] + ".meta.json"
    assert_dossier_key(key)
    return key


def index_key(category: str, name: str, face_slug: str | None = None) -> str:
    if face_slug:
        key = f"dossiers/index/{stable_slug(category)}/{stable_slug(name)}/{stable_slug(face_slug)}.json"
    else:
        key = f"dossiers/index/{stable_slug(category)}/{stable_slug(name)}.json"
    assert_dossier_key(key)
    return key


class DossierStore:
    """Read and write private briefing objects. Implementations must not touch ``public/``."""

    def get_text(self, key: str) -> str | None:
        raise NotImplementedError

    def put_text(self, key: str, text: str) -> None:
        raise NotImplementedError

    def get_json(self, key: str) -> dict | None:
        raw = self.get_text(key)
        if not raw:
            return None
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, dict) else None

    def put_json(self, key: str, payload: dict) -> None:
        self.put_text(key, json.dumps(payload, indent=2, sort_keys=True) + "\n")


class MemoryDossierStore(DossierStore):
    """In-process stand-in for tests and for a dry outline. Nothing is uploaded."""

    def __init__(self) -> None:
        self.objects: dict[str, str] = {}

    def get_text(self, key: str) -> str | None:
        assert_dossier_key(key)
        return self.objects.get(key)

    def put_text(self, key: str, text: str) -> None:
        assert_dossier_key(key)
        self.objects[key] = text


class R2DossierStore(DossierStore):
    """R2-backed briefings. Uses the corpus credentials and a ``dossiers/`` key."""

    def __init__(self, config) -> None:
        self.config = config

    def get_text(self, key: str) -> str | None:
        body = get_private_object(key, config=self.config)
        if body is None:
            return None
        return body.decode("utf-8")

    def put_text(self, key: str, text: str) -> None:
        content_type = "application/json" if key.endswith(".json") else "text/plain; charset=utf-8"
        result = put_private_object(
            key,
            text.encode("utf-8"),
            config=self.config,
            content_type=content_type,
        )
        if result != "uploaded":
            raise RuntimeError("R2 is not configured")


def open_dossier_store():
    """The private bucket, or ``None`` when R2 is not configured.

    A partial R2 configuration still raises, the same as a corpus upload.
    """
    config = load_r2_config()
    if config is None:
        return None
    return R2DossierStore(config)


def load_dossier_text(
    store: DossierStore,
    edition: str,
    planet_id: object,
    perspective_id: object | None = None,
) -> str | None:
    """Read one briefing. Pipeline tools and a future visitor chat use this.

    The read is not a model call. Chat tokens, if a visitor chat is added
    later, are a separate budget from the pipeline's $1/day cap.
    """
    return store.get_text(edition_markdown_key(edition, planet_id, perspective_id))


def load_retrieval_pack(
    store: DossierStore,
    edition: str,
    planet_id: object,
    perspective_id: object | None = None,
) -> dict | None:
    """Briefing markdown plus the stored top-post URIs.

    The caller joins those URIs to the private corpus. Neither piece belongs
    in ``data.json``.
    """
    markdown = load_dossier_text(store, edition, planet_id, perspective_id)
    meta = store.get_json(edition_meta_key(edition, planet_id, perspective_id))
    if markdown is None and not meta:
        return None
    top = list((meta or {}).get("top_n") or [])
    return {
        "markdown": markdown or "",
        "top_n": top,
        "edition": edition,
        "planet_id": str(planet_id),
        "perspective_id": None if perspective_id is None else str(perspective_id),
    }


def top_posts(posts: Sequence[dict], limit: int = TOP_N) -> list[dict]:
    """Highest likes first. URI breaks ties so equal likes do not reshuffle."""
    ranked = sorted(
        list(posts),
        key=lambda post: (
            -int(post.get("likes") or 0),
            post_uri(post),
            str(post.get("author") or ""),
        ),
    )
    return ranked[: max(0, int(limit))]


def sample_posts(posts: Sequence[dict], limit: int = SAMPLE_LIMIT) -> list[dict]:
    """Representative slice for the briefing prompt.

    Uses the same diversity sampler as face labeling when the texts embed.
    Falls back to the like ranking when they do not.
    """
    chosen = [post for post in posts if str(post.get("text") or post.get("clean_text") or "").strip()]
    if len(chosen) <= limit:
        return list(chosen)
    try:
        from pipeline.prompt_sample import select_prompt_posts

        picked = select_prompt_posts(chosen, None, limit=limit)
        if picked:
            return picked
    except (ValueError, ImportError):
        pass
    return top_posts(chosen, limit)


def top_n_records(posts: Sequence[dict]) -> list[dict]:
    return [{"uri": post_uri(post), "likes": int(post.get("likes") or 0)} for post in top_posts(posts)]


def needs_rebuild(stored: dict | None, uris: Sequence[str], top: Sequence[dict]) -> bool:
    """True when the stored briefing is missing or the post set moved enough.

    ``new posts / current posts > 0.20`` rebuilds. Exactly 0.20 reuses.
    A top-8 post rebuilds only when its URI is new to that top 8 and its
    likes are strictly above the previous floor, so a tie at the floor does
    not spend.
    """
    if not stored:
        return True
    if str(stored.get("prompt_version") or "") != DOSSIER_PROMPT_VERSION:
        return True
    if not stored.get("summary") or not stored.get("brief") or not stored.get("detail"):
        return True
    current = [uri for uri in uris if uri]
    if not current:
        return False
    previous = set(stored.get("post_uris") or [])
    fresh = len(set(current) - previous) / len(set(current))
    if fresh > NEW_POST_FRACTION:
        return True
    return _top_n_climbed(list(stored.get("top_n") or []), list(top))


def _top_n_climbed(previous: list[dict], current: list[dict]) -> bool:
    if not current:
        return False
    if not previous:
        return True
    floor = min(int(item.get("likes") or 0) for item in previous)
    seen = {str(item.get("uri") or "") for item in previous}
    for item in current:
        uri = str(item.get("uri") or "")
        likes = int(item.get("likes") or 0)
        if uri and uri not in seen and likes > floor:
            return True
    return False


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _quote_text(post: dict, limit: int = 280) -> str:
    text = _clean(post.get("text") or post.get("clean_text") or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _norm_sentence(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _same_sentence(left: str, right: str) -> bool:
    a = _norm_sentence(left)
    b = _norm_sentence(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 40 and (a in b or b in a):
        return True
    a_set, b_set = set(a.split()), set(b.split())
    if not a_set or not b_set:
        return False
    return len(a_set & b_set) / len(a_set | b_set) >= 0.8


def _headings_present(markdown: str) -> bool:
    for heading in HEADINGS:
        if f"## {heading}" not in markdown:
            return False
    return True


def section_bodies(markdown: str) -> dict[str, str]:
    found = {heading: "" for heading in HEADINGS}
    current: str | None = None
    chunks: dict[str, list[str]] = {heading: [] for heading in HEADINGS}
    for line in str(markdown or "").splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            current = name if name in found else None
            continue
        if current:
            chunks[current].append(line)
    return {heading: "\n".join(chunks[heading]).strip() for heading in HEADINGS}


def _strip_fence(text: str) -> str:
    body = str(text or "").strip()
    if body.startswith("```"):
        body = _FENCE.sub("", body).strip()
    return body


def _parse_reader(raw: str) -> dict | None:
    text = _strip_fence(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def build_dossier_prompt(
    kind: str,
    title: str,
    posts: Sequence[dict],
    rivals: Sequence[str],
    subject_name: str,
    rival_posts: Sequence[dict] = (),
) -> str:
    """The paid briefing prompt. Tests and the cost model call this with no network."""
    shown = list(posts)[:SAMPLE_LIMIT]
    lines = [_post_line(index, post) for index, post in enumerate(shown, start=1)]
    others = [_post_line(index, post) for index, post in enumerate(list(rival_posts)[:6], start=1)]
    rival_line = ", ".join(str(item) for item in rivals if str(item).strip()) or "none named"
    other_block = "\n".join(others) if others else "none"
    return (
        f"Write an internal briefing for this {kind}.\n"
        "Length: 900 to 1800 words, about 2 to 4 pages.\n"
        "Use only the posts below. Do not add a fact, number, handle, or source that is not below.\n"
        "Markdown headings, in this order, each starting with ## :\n"
        + "\n".join(f"## {heading}" for heading in HEADINGS)
        + "\n"
        "Subject: what this is about, in the posts' words.\n"
        "Main arguments: the distinct claims, not one sentence repeated.\n"
        "Evidence and sources cited: numbers, links, and outlets the posts actually cite.\n"
        "Sub-camps: clusters inside this side. If the posts do not split, say so.\n"
        "What the other side says: only claims that appear in the posts or in the named other views.\n"
        "Notable quotes: the handle and the post's words.\n"
        "What changed this week: only a change the dates or the posts show. "
        "If none, say the sample does not show a change.\n"
        f"Kind: {kind}\n"
        f"Title: {title}\n"
        f"Subject name: {subject_name}\n"
        f"Other views: {rival_line}\n"
        f"Posts ({len(lines)}):\n"
        + ("\n".join(lines) if lines else "none")
        + "\nPosts from other views, for the other-side section only:\n"
        + other_block
        + "\n"
    )


def build_reader_prompt(
    kind: str,
    title: str,
    dossier: str,
    top: Sequence[dict],
    rivals: Sequence[str],
) -> str:
    lines = [_post_line(index, post) for index, post in enumerate(list(top)[:TOP_N], start=1)]
    rival_line = ", ".join(str(item) for item in rivals if str(item).strip()) or "none named"
    return (
        "Write the public reading-screen copy from the internal briefing and the top posts.\n"
        'Return JSON only: {"summary": "...", "brief": "...", "detail": "..."}\n'
        "summary is one sentence. It must not appear again in brief or detail.\n"
        "brief is 3 to 5 sentences. Each sentence adds a claim the summary did not state.\n"
        "detail is exactly 3 paragraphs separated by a blank line. "
        "They add evidence, one quote with a handle, and the disagreement. "
        "Do not repeat a sentence from the summary or the brief.\n"
        "Do not add a fact that is not in the briefing or the posts.\n"
        "If this is a planet, the summary names the subject. It is not a copy of one view's sentence.\n"
        f"Kind: {kind}\n"
        f"Title: {title}\n"
        f"Other views: {rival_line}\n"
        f"Top posts:\n" + ("\n".join(lines) if lines else "none") + "\n"
        f"Briefing:\n{dossier}\n"
    )


def _post_line(index: int, post: dict) -> str:
    author = str(post.get("author") or "unknown").lstrip("@")
    likes = int(post.get("likes") or 0)
    created = str(post.get("created_at") or "").strip()
    when = f" created {created}" if created else ""
    return f"{index}. @{author} likes={likes}{when}: {_quote_text(post, 500)}"


def extractive_dossier(
    kind: str,
    title: str,
    posts: Sequence[dict],
    rivals: Sequence[str],
    groups: Sequence[tuple[str, Sequence[dict]]] = (),
) -> str:
    """Section outline filled only with words from the stored posts. No model."""
    sampled = list(posts)
    quotes = top_posts(sampled, 5)
    urls: list[str] = []
    bare_link = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s)]*)?", re.I)
    for post in sampled:
        text = str(post.get("text") or "")
        found = _URL.findall(text) + [
            match for match in bare_link.findall(text) if "bsky.social" not in match.lower()
        ]
        for match in found:
            cleaned = match.rstrip(").,;")
            if cleaned and cleaned not in urls:
                urls.append(cleaned)
    quote_lines = []
    for post in quotes:
        author = str(post.get("author") or "unknown").lstrip("@")
        quote_lines.append(f"- @{author} ({int(post.get('likes') or 0)} likes): “{_quote_text(post)}”")
    if not quote_lines:
        quote_lines.append("- The sample has no post text to quote.")
    argument_lines = []
    seen: set[str] = set()
    for post in top_posts(sampled, 6):
        line = _quote_text(post, 220)
        key = _norm_sentence(line)
        if not key or key in seen:
            continue
        seen.add(key)
        author = str(post.get("author") or "unknown").lstrip("@")
        argument_lines.append(f"- @{author}: {line}")
    if not argument_lines:
        argument_lines.append("- The sample has no post text.")
    if urls:
        evidence = "Links cited in the sampled posts: " + ", ".join(urls[:8]) + "."
    else:
        evidence = "The sampled posts do not include an http link. The lines above are the evidence they do contain."
    if groups:
        camp_lines = []
        for name, group_posts in groups:
            lead = top_posts(list(group_posts), 1)
            if lead:
                author = str(lead[0].get("author") or "unknown").lstrip("@")
                camp_lines.append(
                    f"- {name} ({len(list(group_posts))} posts in this slice). "
                    f"@{author}: “{_quote_text(lead[0], 180)}”"
                )
            else:
                camp_lines.append(f"- {name}: no post text in this slice.")
        camps = "\n".join(camp_lines)
    else:
        camps = "The posts in this sample are one camp. They do not show a further split."
    rival_names = [str(item) for item in rivals if str(item).strip()]
    if kind == "planet" and groups:
        other = (
            "Each camp above is one view in the same sample. "
            "The quotes are the disagreement the posts actually contain."
        )
    elif rival_names:
        other = (
            "Other views named beside this one: "
            + ", ".join(rival_names)
            + ". Their own posts are briefed separately and are not restated here."
        )
    else:
        other = "This sample does not name a second view."
    dates: dict[str, int] = {}
    for post in sampled:
        created = str(post.get("created_at") or "")
        if len(created) >= 10:
            day = created[:10]
            dates[day] = dates.get(day, 0) + 1
    if dates:
        rendered = ", ".join(f"{day} ({count})" for day, count in sorted(dates.items()))
        changed = f"Post dates in this sample: {rendered}. No earlier briefing is in this outline to compare."
    else:
        changed = "This sample has no post dates, so it does not show what changed this week."
    subject = (
        f"{title}: {len(sampled)} posts in this sample. "
        "The lines below are taken from those posts and do not add a claim beyond them."
    )
    parts = [
        f"## {HEADINGS[0]}\n{subject}",
        f"## {HEADINGS[1]}\n" + "\n".join(argument_lines),
        f"## {HEADINGS[2]}\n{evidence}",
        f"## {HEADINGS[3]}\n{camps}",
        f"## {HEADINGS[4]}\n{other}",
        f"## {HEADINGS[5]}\n" + "\n".join(quote_lines),
        f"## {HEADINGS[6]}\n{changed}",
    ]
    return "\n\n".join(parts) + "\n"


def _spare_lines(posts: Sequence[dict], title: str) -> list[str]:
    """Factual lines from the sample, used only when a public tier would otherwise repeat."""
    lines = [
        f"This briefing is built from {len(posts)} sampled posts, not from an invented claim.",
    ]
    if posts:
        lead = top_posts(posts, 1)[0]
        author = str(lead.get("author") or "unknown").lstrip("@")
        lines.append(
            f"The highest-liked post in the sample is by @{author} "
            f"and has {int(lead.get('likes') or 0)} likes."
        )
    authors: list[str] = []
    for post in posts:
        author = str(post.get("author") or "").lstrip("@").strip()
        if author and author not in authors:
            authors.append(author)
    if len(authors) >= 2:
        lines.append(f"Handles in the sample include @{authors[0]} and @{authors[1]}.")
    elif authors:
        lines.append(f"One handle in the sample is @{authors[0]}.")
    lines.append(f"Quotes and cited sources for {title} stay in the private briefing.")
    return [line if line.endswith(".") else line + "." for line in lines]


def enforce_no_repeat(
    *,
    summary: str,
    brief: str,
    detail: str,
    dossier: str,
    forbidden: Sequence[str] = (),
    posts: Sequence[dict],
    title: str,
) -> dict:
    """Keep each public tier from repeating the tier above it, or a face's public lines.

    Summary is one sentence. Brief is the next 3–5 sentences and does not
    contain that sentence. Detail is three paragraphs and does not contain
    a summary or brief sentence. Missing sentences are filled from later
    briefing sections, then from sample facts, not by copying the tier above.
    """
    sections = section_bodies(dossier)
    banned: list[str] = []
    for item in forbidden:
        banned.extend(sentences(str(item)))

    def fresh(candidates: Sequence[str]) -> list[str]:
        kept: list[str] = []
        for sentence in candidates:
            text = _clean(sentence)
            if not text:
                continue
            if any(_same_sentence(text, prior) for prior in banned):
                continue
            if any(_same_sentence(text, prior) for prior in kept):
                continue
            kept.append(text if text[-1] in ".!?" else text + ".")
        return kept

    summary_pool = fresh(sentences(summary) + sentences(sections.get("Subject", "")))
    if not summary_pool:
        summary_pool = fresh(_spare_lines(posts, title))
    if not summary_pool:
        summary_pool = [f"{title} is the subject of this sample."]
    summary_out = summary_pool[0]
    banned.append(summary_out)

    brief_pool = fresh(
        sentences(brief)
        + sentences(sections.get("Main arguments", ""))
        + sentences(sections.get("Sub-camps", ""))
        + sentences(sections.get("Evidence and sources cited", ""))
        + _spare_lines(posts, title)
    )
    brief_out = " ".join(brief_pool[:5])
    for sentence in sentences(brief_out):
        banned.append(sentence)

    raw_paragraphs = [part.strip() for part in str(detail or "").split("\n\n") if part.strip()]
    section_order = [
        "Evidence and sources cited",
        "Notable quotes",
        "What the other side says",
        "What changed this week",
        "Sub-camps",
    ]
    paragraphs: list[str] = []
    for paragraph in raw_paragraphs:
        kept = fresh(sentences(paragraph))
        text = " ".join(kept).strip()
        if len(text) >= 40:
            paragraphs.append(text)
            banned.extend(kept)
        if len(paragraphs) == 3:
            break
    for heading in section_order:
        if len(paragraphs) == 3:
            break
        kept = fresh(sentences(sections.get(heading, "")))
        text = " ".join(kept[:4]).strip()
        if len(text) < 40:
            text = " ".join(fresh([text, *_spare_lines(posts, title)])).strip() if text else ""
            if len(text) < 40:
                extra = fresh(_spare_lines(posts, title))
                text = " ".join(extra[:2]).strip()
        if len(text) >= 40:
            paragraphs.append(text)
            banned.extend(sentences(text))
    while len(paragraphs) < 3:
        extra = fresh(_spare_lines(posts, title))
        text = " ".join(extra[:2]).strip() or f"The private briefing for {title} holds the quotes from this sample."
        if len(text) < 40:
            text = text + " The public line does not restate the sentence above."
        paragraphs.append(text)
        banned.extend(sentences(text))
    return {
        "summary": summary_out,
        "brief": brief_out,
        "detail": "\n\n".join(paragraphs[:3]),
    }


def _planet_rivals(perspectives: Sequence[dict]) -> list[str]:
    """Face titles are the other views only when the planet has more than one."""
    names = [str(face.get("title")) for face in perspectives if face.get("title")]
    return names if len(names) > 1 else []


def _resolve_posts(uris: Sequence[str] | None, by_uri: dict[str, dict], fallback: Sequence[dict] | None) -> list[dict]:
    found = []
    for uri in uris or []:
        post = by_uri.get(str(uri))
        if post is not None:
            found.append(post)
    if found:
        return found
    return list(fallback or [])


def apply_dossiers(
    topic: dict,
    posts: Sequence[dict],
    *,
    generate: Callable[[str], str] | None,
    store: DossierStore | None,
    edition: str,
) -> dict:
    """Fill public tiers from private briefings when the caller passes a model and a store.

    With either missing, the topic is unchanged. Nothing in the briefing
    markdown is attached to the topic, so it cannot land in ``data.json``.
    """
    if generate is None or store is None:
        return topic
    by_uri = {str(post.get("uri")): post for post in posts or [] if post.get("uri")}
    perspectives = [face for face in (topic.get("perspectives") or []) if isinstance(face, dict)]
    try:
        _fill_dossiers(topic, perspectives, by_uri, generate, store, edition)
    finally:
        for target in (topic, *perspectives):
            target.pop("_dossier_action", None)
    return topic


def _fill_dossiers(topic, perspectives, by_uri, generate, store, edition) -> None:
    for face in perspectives:
        others = [
            other
            for other in perspectives
            if other is not face and other.get("title") and other.get("title") != face.get("title")
        ]
        rival_posts: list[dict] = []
        for other in others:
            rival_posts.extend(
                _resolve_posts(other.get("_face_member_uris"), by_uri, other.get("representative_posts"))
            )
        _apply_one(
            face,
            _resolve_posts(face.get("_face_member_uris"), by_uri, face.get("representative_posts")),
            kind="perspective",
            title=str(face.get("title") or topic.get("name") or "View"),
            subject_name=str(topic.get("name") or ""),
            rivals=[str(other.get("title")) for other in others],
            rival_posts=rival_posts[:6],
            groups=(),
            category=str(topic.get("category") or "uncategorized"),
            planet_name=str(topic.get("name") or "planet"),
            planet_id=topic.get("id"),
            perspective_id=face.get("id"),
            generate=generate,
            store=store,
            edition=edition,
            forbidden=(),
        )
    member_posts = _resolve_posts(topic.get("_member_uris"), by_uri, None)
    if not member_posts:
        seen: set[str] = set()
        for face in perspectives:
            for post in face.get("representative_posts") or []:
                key = post_uri(post)
                if key in seen:
                    continue
                seen.add(key)
                member_posts.append(post)
    groups = []
    for face in perspectives:
        groups.append(
            (
                str(face.get("title") or "View"),
                _resolve_posts(face.get("_face_member_uris"), by_uri, face.get("representative_posts")),
            )
        )
    forbidden: list[str] = []
    for face in perspectives:
        forbidden.append(str(face.get("summary") or ""))
        forbidden.append(str(face.get("brief") or ""))
    _apply_one(
        topic,
        member_posts,
        kind="planet",
        title=str(topic.get("name") or "Planet"),
        subject_name=str(topic.get("name") or ""),
        rivals=_planet_rivals(perspectives),
        rival_posts=(),
        groups=groups,
        category=str(topic.get("category") or "uncategorized"),
        planet_name=str(topic.get("name") or "planet"),
        planet_id=topic.get("id"),
        perspective_id=None,
        generate=generate,
        store=store,
        edition=edition,
        forbidden=forbidden,
    )
    wrote = sum(1 for face in perspectives if face.get("_dossier_action") == "wrote")
    reused = sum(1 for face in perspectives if face.get("_dossier_action") == "reused")
    if topic.get("_dossier_action") == "wrote":
        wrote += 1
    elif topic.get("_dossier_action") == "reused":
        reused += 1
    name = topic.get("name") or topic.get("id")
    print(f"Dossier {name}: wrote {wrote}, reused {reused}.")


def _apply_one(
    target: dict,
    posts: list[dict],
    *,
    kind: str,
    title: str,
    subject_name: str,
    rivals: list[str],
    rival_posts: Sequence[dict],
    groups: Sequence[tuple[str, Sequence[dict]]],
    category: str,
    planet_name: str,
    planet_id: object,
    perspective_id: object | None,
    generate: Callable[[str], str],
    store: DossierStore,
    edition: str,
    forbidden: Sequence[str],
) -> None:
    usable = [post for post in posts if str(post.get("text") or post.get("clean_text") or "").strip()]
    if not usable:
        target["_dossier_action"] = "skipped"
        return
    uris = [post_uri(post) for post in usable]
    top = top_n_records(usable)
    face_slug = None if perspective_id is None else f"{perspective_id}-{title}"
    pointer = index_key(category, planet_name, face_slug)
    stored = store.get_json(pointer)
    if stored and not needs_rebuild(stored, uris, top):
        target["summary"] = str(stored.get("summary") or target.get("summary") or "")
        target["brief"] = str(stored.get("brief") or target.get("brief") or "")
        target["detail"] = str(stored.get("detail") or target.get("detail") or "")
        target["_dossier_action"] = "reused"
        return
    sampled = sample_posts(usable, SAMPLE_LIMIT)
    prompt = build_dossier_prompt(kind, title, sampled, rivals, subject_name, rival_posts)
    drafted = _strip_fence(generate(prompt) or "")
    if not _headings_present(drafted):
        drafted = extractive_dossier(kind, title, sampled, rivals, groups)
    reader_prompt = build_reader_prompt(kind, title, drafted, top_posts(usable, TOP_N), rivals)
    parsed = _parse_reader(generate(reader_prompt) or "") or {}
    reader = enforce_no_repeat(
        summary=str(parsed.get("summary") or ""),
        brief=str(parsed.get("brief") or ""),
        detail=str(parsed.get("detail") or ""),
        dossier=drafted,
        forbidden=forbidden,
        posts=sampled,
        title=title,
    )
    markdown_key = edition_markdown_key(edition, planet_id, perspective_id)
    meta_key = edition_meta_key(edition, planet_id, perspective_id)
    record = {
        "prompt_version": DOSSIER_PROMPT_VERSION,
        "edition": edition,
        "kind": kind,
        "name": title,
        "markdown_key": markdown_key,
        "post_uris": sorted(set(uris)),
        "top_n": top,
        "summary": reader["summary"],
        "brief": reader["brief"],
        "detail": reader["detail"],
    }
    store.put_text(markdown_key, drafted if drafted.endswith("\n") else drafted + "\n")
    store.put_json(meta_key, record)
    store.put_json(pointer, record)
    target["summary"] = reader["summary"]
    target["brief"] = reader["brief"]
    target["detail"] = reader["detail"]
    target["_dossier_action"] = "wrote"


def planning_posts(count: int, chars: int = PLANNING_POST_CHARS) -> list[dict]:
    """Fixed-length posts for the nightly token estimate. Not a real sample."""
    posts = []
    width = max(20, int(chars))
    for index in range(count):
        suffix = f" {index:04d}"
        filler = ("detail " * 80)[: width]
        text = (filler + suffix)[:width]
        if len(text) < width:
            text = text + ("x" * (width - len(text)))
        posts.append(
            {
                "uri": f"at://plan/post/{index}",
                "author": f"reader{index}.bsky.social",
                "text": text,
                "likes": max(0, count - index),
                "created_at": "2026-10-18T12:00:00Z",
            }
        )
    return posts


def project_pair(
    posts: Sequence[dict],
    *,
    kind: str,
    title: str,
    rivals: Sequence[str] = (),
    output_tokens: int,
) -> dict:
    """Input tokens from the real prompt. Output tokens are the planning budget."""
    sampled = list(posts)[:SAMPLE_LIMIT]
    dossier_prompt = build_dossier_prompt(kind, title, sampled, rivals, title)
    placeholder = "w" * int(Decimal(output_tokens) * CHARS_PER_TOKEN)
    reader_prompt = build_reader_prompt(kind, title, placeholder, top_posts(sampled, TOP_N), rivals)
    dossier_in = estimate_tokens(dossier_prompt)
    reader_in = estimate_tokens(reader_prompt)
    dossier_usd = price_tokens(dossier_in, output_tokens)
    reader_usd = price_tokens(reader_in, READER_OUTPUT_TOKENS)
    return {
        "dossier_input_tokens": dossier_in,
        "dossier_output_tokens": int(output_tokens),
        "reader_input_tokens": reader_in,
        "reader_output_tokens": READER_OUTPUT_TOKENS,
        "usd": dossier_usd + reader_usd,
    }


def project_topic(topic: dict, *, output_tokens: int) -> dict:
    """Upper-bound cost to brief one stored planet and each of its perspectives."""
    faces = [face for face in (topic.get("perspectives") or []) if isinstance(face, dict)]
    planet_posts: list[dict] = []
    seen: set[str] = set()
    per_face = []
    for face in faces:
        face_posts = list(face.get("representative_posts") or [])
        for post in face_posts:
            key = post_uri(post)
            if key in seen:
                continue
            seen.add(key)
            planet_posts.append(post)
        sampled = sample_posts(face_posts, SAMPLE_LIMIT)
        rivals = [str(other.get("title")) for other in faces if other is not face and other.get("title")]
        pair = project_pair(
            sampled,
            kind="perspective",
            title=str(face.get("title") or "View"),
            rivals=rivals,
            output_tokens=output_tokens,
        )
        per_face.append({"id": face.get("id"), "title": face.get("title"), **pair})
    planet_pair = project_pair(
        sample_posts(planet_posts, SAMPLE_LIMIT),
        kind="planet",
        title=str(topic.get("name") or "Planet"),
        rivals=[str(face.get("title")) for face in faces if face.get("title")],
        output_tokens=output_tokens,
    )
    total = planet_pair["usd"] + sum((item["usd"] for item in per_face), Decimal("0"))
    calls = 2 * (1 + len(faces))
    return {
        "name": topic.get("name"),
        "faces": len(faces),
        "calls": calls,
        "planet": planet_pair,
        "perspectives": per_face,
        "usd": total,
    }


def project_nightly(
    *,
    planets: int = PLANNING_PLANETS,
    faces_per_planet: int = PLANNING_FACES_PER_PLANET,
    output_tokens: int = DOSSIER_OUTPUT_TOKENS_4PAGE,
    rebuild_fraction: Decimal | float | str = 1,
    post_chars: int = PLANNING_POST_CHARS,
) -> dict:
    """Cost of briefing ``planets`` at ``rebuild_fraction`` of a full rebuild.

    Fraction 1 rebuilds every briefing every night. Fraction 0 reuses all of
    them. The post length is the seed corpus mean, and each prompt carries
    the 40-post sample cap.
    """
    posts = planning_posts(SAMPLE_LIMIT, post_chars)
    pair = project_pair(posts, kind="planet", title="Planning planet", output_tokens=output_tokens)
    units = int(planets) * (1 + int(faces_per_planet))
    full = (pair["usd"] * units).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    fraction = Decimal(str(rebuild_fraction))
    spent = (full * fraction).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    return {
        "planets": int(planets),
        "faces_per_planet": int(faces_per_planet),
        "units": units,
        "calls": units * 2,
        "pair": pair,
        "full_rebuild_usd": full,
        "rebuild_fraction": fraction,
        "usd": spent,
    }


def _load_topics(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    topics = list(payload.get("topics") or [])
    sections = payload.get("sections") or {}
    if isinstance(sections, dict):
        for section_topics in sections.values():
            if isinstance(section_topics, list):
                topics.extend(section_topics)
    return [topic for topic in topics if isinstance(topic, dict)]


def _select_topics(topics: list[dict], names: Sequence[str]) -> list[dict]:
    wanted = [name.casefold() for name in names]
    found = []
    missing = []
    by_name = {str(topic.get("name") or "").casefold(): topic for topic in topics}
    for name in wanted:
        topic = by_name.get(name)
        if topic is None:
            missing.append(name)
        else:
            found.append(topic)
    if missing:
        known = ", ".join(str(topic.get("name")) for topic in topics[:12])
        raise SystemExit(f"Unknown planet(s): {', '.join(missing)}. Known names start: {known}")
    return found


def _format_usd(amount: Decimal) -> str:
    return f"${amount:.6f}"


def format_topic_report(topic_cost: dict) -> str:
    lines = [
        f"{topic_cost['name']}: {topic_cost['faces']} perspective(s), "
        f"{topic_cost['calls']} model calls, {_format_usd(topic_cost['usd'])}"
    ]
    planet = topic_cost["planet"]
    lines.append(
        "  planet dossier in/out "
        f"{planet['dossier_input_tokens']}/{planet['dossier_output_tokens']} tokens; "
        f"reader in/out {planet['reader_input_tokens']}/{planet['reader_output_tokens']}"
    )
    for face in topic_cost["perspectives"]:
        lines.append(
            f"  {face['title']}: dossier in {face['dossier_input_tokens']}, "
            f"reader in {face['reader_input_tokens']}"
        )
    return "\n".join(lines)


def sample_report(topics: list[dict]) -> str:
    """Cost text for a named-planet sample. Does not call a model."""
    ceiling = []
    overshoot_tokens = int(Decimal(DOSSIER_OUTPUT_TOKENS_4PAGE) * OUTPUT_OVERSHOOT)
    blocks = ["Dossier sample cost. No model was called.", "Prices: Llama 3.3 70B Turbo $0.10 / $0.32 per 1M tokens."]
    blocks.append("Output budget is the 4-page ceiling (1,800 words, 2,500 tokens) unless noted.")
    total_ceiling = Decimal("0")
    total_overshoot = Decimal("0")
    total_floor = Decimal("0")
    for topic in topics:
        high = project_topic(topic, output_tokens=DOSSIER_OUTPUT_TOKENS_4PAGE)
        low = project_topic(topic, output_tokens=DOSSIER_OUTPUT_TOKENS_2PAGE)
        over = project_topic(topic, output_tokens=overshoot_tokens)
        ceiling.append(high)
        total_ceiling += high["usd"]
        total_floor += low["usd"]
        total_overshoot += over["usd"]
        blocks.append(format_topic_report(high))
        blocks.append(f"  2-page floor: {_format_usd(low['usd'])}; 20% output overshoot: {_format_usd(over['usd'])}")
    blocks.append(
        f"Sample total at 4-page ceiling: {_format_usd(total_ceiling)}. "
        f"2-page floor: {_format_usd(total_floor)}. "
        f"Approve up to {_format_usd(total_overshoot)} if the model overruns by 20%."
    )
    steady = project_nightly(rebuild_fraction=0)
    every = project_nightly(rebuild_fraction=1)
    first = project_nightly(rebuild_fraction=1, output_tokens=overshoot_tokens)
    blocks.append(
        f"Nightly, rebuild every briefing ({every['planets']} planets, "
        f"{every['faces_per_planet']} perspectives each, {every['calls']} calls): "
        f"{_format_usd(every['full_rebuild_usd'])} at the 4-page ceiling, "
        f"{_format_usd(first['full_rebuild_usd'])} with a 20% overrun."
    )
    blocks.append(
        "Nightly under the rebuild policy when no planet is over 20% new posts "
        f"and no top-{TOP_N} post climbs the like floor: {_format_usd(steady['usd'])}."
    )
    blocks.append(
        "This spend is pipeline labeling spend and counts against the $1/day cap. "
        "It is not a visitor-chat budget."
    )
    return "\n".join(blocks) + "\n"


def _real_generate(prompt: str) -> str:
    from pipeline.label import _openai_generate, resolve_openai_model
    from pipeline.spend_cap import guard_before_paid_call

    guard_before_paid_call("dossier")
    return _openai_generate(prompt, resolve_openai_model(None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private planet and perspective dossiers")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="Project the cost of briefing named planets")
    sample.add_argument("--data", type=Path, default=Path("public/data.json"))
    sample.add_argument("--planets", nargs="+", required=True)
    sample.add_argument(
        "--run",
        action="store_true",
        help="Spend: call the labeling model and write R2. Omit to print the cost only.",
    )
    sample.add_argument("--edition", default="")
    outline = commands.add_parser("outline", help="Print an extractive outline from stored posts")
    outline.add_argument("--data", type=Path, default=Path("public/data.json"))
    outline.add_argument("--planets", nargs="+", required=True)
    args = parser.parse_args(argv)
    topics = _select_topics(_load_topics(args.data), args.planets)
    if args.command == "outline":
        for topic in topics:
            faces = list(topic.get("perspectives") or [])
            posts: list[dict] = []
            groups = []
            for face in faces:
                face_posts = list(face.get("representative_posts") or [])
                posts.extend(face_posts)
                groups.append((str(face.get("title") or "View"), face_posts))
            print(f"# {topic.get('name')}")
            print(
                extractive_dossier(
                    "planet",
                    str(topic.get("name") or ""),
                    posts,
                    _planet_rivals(faces),
                    groups,
                )
            )
            for face in faces:
                rivals = [str(other.get("title")) for other in faces if other is not face]
                print(f"# {topic.get('name')} / {face.get('title')}")
                print(
                    extractive_dossier(
                        "perspective",
                        str(face.get("title") or ""),
                        list(face.get("representative_posts") or []),
                        rivals,
                    )
                )
        return 0
    print(sample_report(topics), end="")
    if not args.run:
        print("Dry run. Re-invoke with --run only after the cost above is approved.")
        return 0
    from pipeline.pipeline_overlap import EXIT_CLEAR, check_pipeline_overlap

    overlap = check_pipeline_overlap()
    if overlap.error:
        print(f"Pipeline overlap check failed: {overlap.error}", file=sys.stderr)
        print("Not calling the model.", file=sys.stderr)
        return 3
    if not overlap.clear:
        print("A Daily Discourse Pipeline run is queued or in progress. Not calling the model.", file=sys.stderr)
        return 2
    store = open_dossier_store()
    if store is None:
        print("R2 is not configured. Not calling the model.", file=sys.stderr)
        return 1
    edition = args.edition.strip() or datetime.now(timezone.utc).date().isoformat()
    for topic in topics:
        apply_dossiers(topic, [], generate=_real_generate, store=store, edition=edition)
        blob = json.dumps({"summary": topic.get("summary"), "brief": topic.get("brief"), "detail": topic.get("detail")})
        if "dossiers/" in blob:
            raise RuntimeError("Refusing to print a private key in the public fields")
        print(f"Wrote private briefings for {topic.get('name')} on {edition}. Public fields were not saved to data.json.")
    return EXIT_CLEAR


if __name__ == "__main__":
    raise SystemExit(main())
