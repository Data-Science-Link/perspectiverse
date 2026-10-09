"""Compare today's per-post Jev call with the batched spam+claim request.

Phase 3 stays off. The planet-level section call is not in the live
pipeline; ``--planets`` is the optional shadow test for #90.

The cloud agent does not run this. It spends money. With TYPESAFE_API_KEY set:

    python scripts/jev_shadow_test.py --db pipeline/data/live_corpus.db --posts 40

    python scripts/jev_shadow_test.py --planets planets.json

The hard cap is $0.03 of Jev input tokens for the whole script, even if
--max-spend is higher and even if both modes run. A run stops before the
next call that would cross the cap.

Post mode reports claim agreement (bar >= 95%) and claims lost (bar <= 3%).
Planet mode reports agreement with the majority of each planet's existing
per-post sections (bar >= 90%).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

# Repo root on the path when this file is run as a script.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.costs import (  # noqa: E402
    JEV_BATCH_QUESTION_TOKENS,
    JEV_PLANET_SECTION_TOKENS,
    JEV_POST_TEXT_TOKENS,
    JEV_REQUEST_OVERHEAD_TOKENS,
    jev_cost_usd,
)
from pipeline.jev import (  # noqa: E402
    BATCH_SIZE,
    CLAIM_THRESHOLD,
    SPAM_THRESHOLD,
    _classify_post,
)

MAX_SPEND_USD = Decimal("0.03")
# #27's per-call assumption. Used only to decide whether the next call fits.
# The report's token counts come from the response, not from this guess.
ASSUMED_TOKENS_PER_POST = 600
CLAIM_AGREEMENT_BAR = Decimal("0.95")
SECTION_AGREEMENT_BAR = Decimal("0.90")
CLAIMS_LOST_BAR = Decimal("0.03")


def call_would_exceed(spent: Decimal, tokens: int, cap: Decimal = MAX_SPEND_USD) -> bool:
    """True when starting a call of about ``tokens`` would pass the cap."""
    return spent + jev_cost_usd(tokens) > cap


def clamp_spend_cap(requested: Decimal) -> Decimal:
    """The shadow test cannot be pointed at more than $0.03."""
    if requested <= 0:
        return MAX_SPEND_USD
    return min(requested, MAX_SPEND_USD)


def batch_call_token_estimate(count: int) -> int:
    """One batched spam+claim request: overhead once, then post text and two questions."""
    if count <= 0:
        return 0
    per_post = JEV_POST_TEXT_TOKENS + 2 * JEV_BATCH_QUESTION_TOKENS
    return JEV_REQUEST_OVERHEAD_TOKENS + count * per_post


def chunk_token_estimate(count: int) -> int:
    """Worst case for ``count`` posts: a per-post call each, then one spam+claim batch."""
    if count <= 0:
        return 0
    return count * ASSUMED_TOKENS_PER_POST + batch_call_token_estimate(count)


def kept_claim(decision: dict | None) -> bool:
    """A claim the live path would keep: not spam, and the claim noul clears 0.5."""
    if not isinstance(decision, dict):
        return False
    spam = decision.get("spam_score")
    if spam is not None and float(spam) >= SPAM_THRESHOLD:
        return False
    return decision.get("is_claim") is True


def agreement_report(per_post: list[dict | None], batched: list[dict | None]) -> dict[str, object]:
    """Claim agreement and claims lost on paired decisions.

    Posts where either side failed (None) are left out of the rates and counted
    as failures. The batch does not ask for a section, so section is not a bar
    here. A batched non-claim counts as a lost claim.
    """
    if len(per_post) != len(batched):
        raise ValueError("per-post and batched results must be the same length")
    compared = 0
    claim_matches = 0
    per_claims = 0
    lost = 0
    failures = 0
    for left, right in zip(per_post, batched):
        if left is None or right is None:
            failures += 1
            continue
        compared += 1
        left_claim = kept_claim(left)
        right_claim = kept_claim(right)
        if left_claim == right_claim:
            claim_matches += 1
        if left_claim:
            per_claims += 1
            if not right_claim:
                lost += 1
    return {
        "compared": compared,
        "failures": failures,
        "claim_agreement": _rate(claim_matches, compared),
        "claims_lost": _rate(lost, per_claims),
        "per_post_claims": per_claims,
        "claims_lost_count": lost,
        "claim_bar": CLAIM_AGREEMENT_BAR,
        "lost_bar": CLAIMS_LOST_BAR,
        "claim_pass": _rate(claim_matches, compared) >= CLAIM_AGREEMENT_BAR if compared else False,
        "lost_pass": _rate(lost, per_claims) <= CLAIMS_LOST_BAR if per_claims else False,
    }


def _rate(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)


def _meter_input_tokens() -> int:
    from pipeline.costs import SERVICE_JEV, get_meter

    return sum(attempt.input_tokens for attempt in get_meter().attempts() if attempt.service == SERVICE_JEV)


def _real_per_post(post: dict) -> tuple[dict | None, int]:
    before = _meter_input_tokens()
    decision = _classify_post(post)
    return decision, _meter_input_tokens() - before


def _real_batch(posts: list[dict], spent: Decimal, cap: Decimal) -> tuple[list[dict | None], int]:
    """One spam+claim request. No section call."""
    from pipeline.jev import _post_systemone, parse_spam_claim_batch, spam_claim_batch_body

    if call_would_exceed(spent, batch_call_token_estimate(len(posts)), cap):
        return [None] * len(posts), 0
    before = _meter_input_tokens()
    texts = [post_text_of(post)[:4000] for post in posts]
    try:
        payload = _post_systemone(spam_claim_batch_body(texts))
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return [None] * len(posts), _meter_input_tokens() - before
    model, scores = parse_spam_claim_batch(payload, len(posts))
    decisions: list[dict | None] = []
    for pair in scores:
        if pair is None:
            decisions.append(None)
            continue
        spam_score, claim_score = pair
        decisions.append(
            {
                "spam_score": spam_score,
                "claim_score": claim_score,
                "section": None,
                "section_confidence": None,
                "is_claim": claim_score >= CLAIM_THRESHOLD,
                "model": model,
            }
        )
    return decisions, _meter_input_tokens() - before


def post_text_of(post: dict) -> str:
    from pipeline.jev_prefilter import post_text

    return post_text(post)


def run_shadow(
    posts: list[dict],
    *,
    cap: Decimal = MAX_SPEND_USD,
    per_post_call=_real_per_post,
    batch_call=_real_batch,
) -> dict[str, object]:
    """Score the same posts both ways, stopping before the cap.

    ``per_post_call`` and ``batch_call`` return ``(decision, input_tokens)``.
    The default closures hit the TypeSafe API. Tests pass fakes.
    """
    limit = clamp_spend_cap(cap)
    spent = Decimal("0")
    per_tokens = 0
    batch_tokens = 0
    per_calls = 0
    batch_calls = 0
    paired_left: list[dict | None] = []
    paired_right: list[dict | None] = []
    index = 0
    while index < len(posts):
        room = 0
        projected = spent
        while room < BATCH_SIZE and index + room < len(posts):
            nxt = chunk_token_estimate(room + 1) - chunk_token_estimate(room)
            if call_would_exceed(projected, nxt, limit):
                break
            projected += jev_cost_usd(nxt)
            room += 1
        if room == 0:
            break
        chunk = posts[index : index + room]
        finished: list[tuple[dict, dict | None, int]] = []
        for post in chunk:
            if call_would_exceed(spent, ASSUMED_TOKENS_PER_POST, limit):
                break
            decision, tokens = per_post_call(post)
            per_calls += 1
            spent += jev_cost_usd(int(tokens))
            finished.append((post, decision, int(tokens)))
            if spent > limit:
                break
        comparable = [(post, decision, tokens) for post, decision, tokens in finished if decision is not None]
        if not comparable:
            index += len(finished)
            if spent > limit:
                break
            continue
        if call_would_exceed(spent, batch_call_token_estimate(len(comparable)), limit):
            index += len(finished)
            break
        batched, tokens = batch_call([post for post, _decision, _tokens in comparable], spent, limit)
        batch_calls += 1
        batch_tokens += int(tokens)
        spent += jev_cost_usd(int(tokens))
        if len(batched) != len(comparable):
            raise RuntimeError("batched scorer returned a different number of posts")
        for (_post, left, used), right in zip(comparable, batched):
            paired_left.append(left)
            paired_right.append(right)
            per_tokens += used
        index += len(finished)
        if spent > limit:
            break
    report = agreement_report(paired_left, paired_right)
    counted = len(paired_left)
    report.update(
        {
            "posts_both_ways": counted,
            "spent_usd": spent,
            "cap_usd": limit,
            "per_post_calls": per_calls,
            "batch_calls": batch_calls,
            "per_post_input_tokens": per_tokens,
            "batch_input_tokens": batch_tokens,
            "per_post_usd": jev_cost_usd(per_tokens),
            "batch_usd": jev_cost_usd(batch_tokens),
            "per_post_usd_per_post": _per(jev_cost_usd(per_tokens), counted),
            "batch_usd_per_post": _per(jev_cost_usd(batch_tokens), counted),
            "per_post_tokens_per_post": _per(Decimal(per_tokens), counted),
            "batch_tokens_per_post": _per(Decimal(batch_tokens), counted),
            "stopped_early": index < len(posts),
        }
    )
    return report


def _per(total: Decimal, count: int) -> Decimal:
    if count <= 0:
        return Decimal("0")
    return total / Decimal(count)


def arguments_text(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def majority_sections(sections: list[str]) -> list[str]:
    """Sections tied for the most member posts. Empty when none were stored."""
    counts = Counter(str(item).strip() for item in sections if str(item or "").strip())
    if not counts:
        return []
    best = max(counts.values())
    return sorted(name for name, count in counts.items() if count == best)


def _real_planet(planet: dict, spent: Decimal, cap: Decimal) -> tuple[str | None, int]:
    from pipeline.jev import _post_systemone, parse_planet_section, planet_section_body

    if call_would_exceed(spent, JEV_PLANET_SECTION_TOKENS, cap):
        return None, 0
    before = _meter_input_tokens()
    try:
        payload = _post_systemone(
            planet_section_body(str(planet.get("summary") or ""), arguments_text(planet.get("arguments")))
        )
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return None, _meter_input_tokens() - before
    parsed = parse_planet_section(payload)
    if parsed is None:
        return None, _meter_input_tokens() - before
    _model, choice, _confidence = parsed
    return choice, _meter_input_tokens() - before


def run_planet_shadow(
    planets: list[dict],
    *,
    spent: Decimal = Decimal("0"),
    cap: Decimal = MAX_SPEND_USD,
    planet_call=_real_planet,
) -> dict[str, object]:
    """One Jev section call per planet, compared with the per-post majority.

    ``planet_call`` returns ``(section or None, input_tokens)``. The default
    hits the TypeSafe API. Spend continues from ``spent`` so a post comparison
    in the same process shares the cap.
    """
    limit = clamp_spend_cap(cap)
    tokens = 0
    calls = 0
    failures = 0
    skipped = 0
    compared: list[dict[str, object]] = []
    index = 0
    eligible = 0
    for planet in planets:
        winners = majority_sections(list(planet.get("sections") or []))
        summary = str(planet.get("summary") or "").strip()
        arguments = arguments_text(planet.get("arguments"))
        if not winners or not (summary or arguments):
            skipped += 1
            continue
        eligible += 1
        if call_would_exceed(spent, JEV_PLANET_SECTION_TOKENS, limit):
            break
        choice, used = planet_call(planet, spent, limit)
        calls += 1
        used = int(used)
        tokens += used
        spent += jev_cost_usd(used)
        index += 1
        if not choice:
            failures += 1
        else:
            compared.append(
                {
                    "name": str(planet.get("name") or planet.get("id") or f"planet-{index}"),
                    "majority": winners,
                    "choice": choice,
                    "agree": choice in winners,
                }
            )
        if spent > limit:
            break
    agrees = sum(1 for row in compared if row["agree"])
    rate = _rate(agrees, len(compared))
    return {
        "planets_compared": len(compared),
        "failures": failures,
        "skipped": skipped,
        "agreement": rate,
        "agreement_bar": SECTION_AGREEMENT_BAR,
        "agreement_pass": rate >= SECTION_AGREEMENT_BAR if compared else False,
        "disagreements": [row for row in compared if not row["agree"]],
        "calls": calls,
        "input_tokens": tokens,
        "usd": jev_cost_usd(tokens),
        "usd_per_planet": _per(jev_cost_usd(tokens), len(compared)),
        "tokens_per_planet": _per(Decimal(tokens), len(compared)),
        "spent_usd": spent,
        "cap_usd": limit,
        "stopped_early": index < eligible,
    }


def _load_posts(db: Path | None, blob: Path | None, count: int) -> list[dict]:
    if db is not None:
        from pipeline.store import connect, load_posts

        connection = connect(db)
        try:
            posts = load_posts(connection)
        finally:
            connection.close()
    elif blob is not None:
        loaded = json.loads(blob.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError("--json must be a list of posts")
        posts = loaded
    else:
        raise ValueError("Pass --db or --json")
    usable = [post for post in posts if post_text_of(post)]
    if count > 0:
        usable = usable[-count:]
    return usable


def _load_planets(path: Path) -> list[dict]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("--planets must be a list")
    planets = []
    for item in loaded:
        if not isinstance(item, dict):
            raise ValueError("--planets entries must be objects")
        planets.append(item)
    return planets


def format_report(report: dict[str, object]) -> str:
    def pct(value: object) -> str:
        return f"{(Decimal(str(value)) * 100):.1f}%"

    def money(value: object) -> str:
        return f"${Decimal(str(value)):.6f}"

    lines = [
        f"Posts scored both ways: {report['posts_both_ways']}",
        f"Spend so far: {money(report['spent_usd'])} of {money(report['cap_usd'])} cap",
        (
            f"Per-post: {report['per_post_calls']} calls, "
            f"{report['per_post_input_tokens']} input tokens, "
            f"{money(report['per_post_usd'])} total, "
            f"{money(report['per_post_usd_per_post'])} per post, "
            f"{report['per_post_tokens_per_post']} tokens per post"
        ),
        (
            f"Batched spam+claim: {report['batch_calls']} calls, "
            f"{report['batch_input_tokens']} input tokens, "
            f"{money(report['batch_usd'])} total, "
            f"{money(report['batch_usd_per_post'])} per post, "
            f"{report['batch_tokens_per_post']} tokens per post"
        ),
        (
            f"Claim agreement: {pct(report['claim_agreement'])} "
            f"(bar {pct(report['claim_bar'])}) {'PASS' if report['claim_pass'] else 'FAIL'}"
        ),
        (
            f"Claims lost: {pct(report['claims_lost'])} "
            f"({report['claims_lost_count']} of {report['per_post_claims']}; "
            f"bar {pct(report['lost_bar'])}) {'PASS' if report['lost_pass'] else 'FAIL'}"
        ),
        f"Failures left out of the rates: {report['failures']}",
        f"Stopped before the requested posts were all scored: {report['stopped_early']}",
        f"Claim threshold {CLAIM_THRESHOLD}, spam threshold {SPAM_THRESHOLD}, batch size {BATCH_SIZE}.",
        "Section is not asked in the batch. Use --planets for the section bar.",
    ]
    return "\n".join(lines)


def format_planet_report(report: dict[str, object]) -> str:
    def pct(value: object) -> str:
        return f"{(Decimal(str(value)) * 100):.1f}%"

    def money(value: object) -> str:
        return f"${Decimal(str(value)):.6f}"

    lines = [
        f"Planets compared: {report['planets_compared']}",
        f"Spend so far: {money(report['spent_usd'])} of {money(report['cap_usd'])} cap",
        (
            f"Planet section calls: {report['calls']}, "
            f"{report['input_tokens']} input tokens, "
            f"{money(report['usd'])} total, "
            f"{money(report['usd_per_planet'])} per planet, "
            f"{report['tokens_per_planet']} tokens per planet"
        ),
        (
            f"Section agreement with the per-post majority: {pct(report['agreement'])} "
            f"(bar {pct(report['agreement_bar'])}) {'PASS' if report['agreement_pass'] else 'FAIL'}"
        ),
        f"Failures left out of the rate: {report['failures']}",
        f"Planets skipped (no summary or no member sections): {report['skipped']}",
        f"Stopped before every planet was scored: {report['stopped_early']}",
    ]
    disagreements = report["disagreements"]
    if isinstance(disagreements, list) and disagreements:
        lines.append("Disagreements:")
        for row in disagreements:
            if not isinstance(row, dict):
                continue
            majority = ", ".join(row.get("majority") or [])
            lines.append(f"  {row.get('name')}: Jev {row.get('choice')}, majority {majority}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow-test batched Jev against one call per post")
    parser.add_argument("--db", type=Path, default=None, help="Retained corpus SQLite path")
    parser.add_argument("--json", type=Path, default=None, help="JSON list of posts")
    parser.add_argument("--posts", type=int, default=40, help="How many posts to try (newest first)")
    parser.add_argument(
        "--planets",
        type=Path,
        default=None,
        help="JSON list of planets (summary, arguments, sections) for the section test",
    )
    parser.add_argument(
        "--max-spend",
        type=Decimal,
        default=MAX_SPEND_USD,
        help="Dollar cap for the whole script. Values above 0.03 are clamped.",
    )
    args = parser.parse_args(argv)
    key = (__import__("os").getenv("TYPESAFE_API_KEY") or "").strip()
    if not key:
        print("TYPESAFE_API_KEY is unset. Not calling TypeSafe. Set the key and rerun this script.", file=sys.stderr)
        print("Hard spend cap: $0.03.")
        print("Posts: python scripts/jev_shadow_test.py --db pipeline/data/live_corpus.db --posts 40")
        print("Planets: python scripts/jev_shadow_test.py --planets planets.json")
        return 2
    if args.db is None and args.json is None and args.planets is None:
        print("Pass --db, --json, or --planets.", file=sys.stderr)
        return 1
    from pipeline.costs import reset_meter

    reset_meter()
    limit = clamp_spend_cap(args.max_spend)
    spent = Decimal("0")
    if args.db is not None or args.json is not None:
        posts = _load_posts(args.db, args.json, args.posts)
        if not posts:
            print("No posts to score.", file=sys.stderr)
            return 1
        report = run_shadow(posts, cap=limit)
        print(format_report(report))
        spent = Decimal(str(report["spent_usd"]))
    if args.planets is not None:
        planets = _load_planets(args.planets)
        if not planets:
            print("No planets to score.", file=sys.stderr)
            return 1
        planet_report = run_planet_shadow(planets, spent=spent, cap=limit)
        print(format_planet_report(planet_report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
