"""Compare today's per-post Jev call with the batched request. Phase 3 stays off.

The cloud agent does not run this. It spends money. With TYPESAFE_API_KEY set:

    python scripts/jev_shadow_test.py --db pipeline/data/live_corpus.db --posts 40

The hard cap is $0.03 of Jev input tokens, even if --max-spend is higher.
A run stops before the next call that would cross the cap. Agreement is
reported only for posts that were scored both ways.

Bars, from the 2026-10-08 quality decision: claim agreement >= 95%,
section agreement >= 90%, claims lost <= 3%.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

# Repo root on the path when this file is run as a script.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.costs import jev_cost_usd  # noqa: E402
from pipeline.jev import (  # noqa: E402
    BATCH_SIZE,
    CLAIM_THRESHOLD,
    SPAM_THRESHOLD,
    _classify_post,
)
from pipeline.jev_prefilter import post_text  # noqa: E402

MAX_SPEND_USD = Decimal("0.03")
# #27's per-call assumption. Used only to decide whether the next call fits.
# The report's token counts come from the response, not from this guess.
ASSUMED_TOKENS_PER_POST = 600
ASSUMED_BATCH_OVERHEAD = 280
ASSUMED_STAGE1_TOKENS_PER_POST = 77
ASSUMED_STAGE2_TOKENS_PER_CLAIM = 103
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


def chunk_token_estimate(count: int) -> int:
    """Worst case for ``count`` posts: a per-post call each, then both batch stages."""
    if count <= 0:
        return 0
    per_post = count * ASSUMED_TOKENS_PER_POST
    stage1 = ASSUMED_BATCH_OVERHEAD + count * ASSUMED_STAGE1_TOKENS_PER_POST
    stage2 = ASSUMED_BATCH_OVERHEAD + count * ASSUMED_STAGE2_TOKENS_PER_CLAIM
    return per_post + stage1 + stage2


def kept_claim(decision: dict | None) -> bool:
    """A claim the live path would keep: not spam, and the claim noul clears 0.5."""
    if not isinstance(decision, dict):
        return False
    spam = decision.get("spam_score")
    if spam is not None and float(spam) >= SPAM_THRESHOLD:
        return False
    return decision.get("is_claim") is True


def agreement_report(per_post: list[dict | None], batched: list[dict | None]) -> dict[str, object]:
    """Claim agreement, section agreement, and claims lost on paired decisions.

    Posts where either side failed (None) are left out of the rates and counted
    as failures. Section agreement uses posts the per-post path kept as claims.
    A batched non-claim counts as a section miss and as a lost claim.
    """
    if len(per_post) != len(batched):
        raise ValueError("per-post and batched results must be the same length")
    compared = 0
    claim_matches = 0
    section_posts = 0
    section_matches = 0
    per_claims = 0
    lost = 0
    failures = 0
    spam_posts = 0
    spam_still_claims = 0
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
            section_posts += 1
            if not right_claim:
                lost += 1
            elif str(right.get("section") or "") == str(left.get("section") or ""):
                section_matches += 1
        spam = left.get("spam_score")
        if spam is not None and float(spam) >= SPAM_THRESHOLD:
            spam_posts += 1
            if right_claim:
                spam_still_claims += 1
    return {
        "compared": compared,
        "failures": failures,
        "claim_agreement": _rate(claim_matches, compared),
        "section_agreement": _rate(section_matches, section_posts),
        "claims_lost": _rate(lost, per_claims),
        "per_post_claims": per_claims,
        "claims_lost_count": lost,
        "spam_posts": spam_posts,
        "spam_still_claims": spam_still_claims,
        "claim_bar": CLAIM_AGREEMENT_BAR,
        "section_bar": SECTION_AGREEMENT_BAR,
        "lost_bar": CLAIMS_LOST_BAR,
        "claim_pass": _rate(claim_matches, compared) >= CLAIM_AGREEMENT_BAR if compared else False,
        "section_pass": _rate(section_matches, section_posts) >= SECTION_AGREEMENT_BAR if section_posts else False,
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
    """Claim batch, then a section batch only when that call still fits under the cap."""
    from pipeline.jev import claim_batch_body, parse_claim_batch, parse_section_batch, section_batch_body, _post_systemone

    before = _meter_input_tokens()
    texts = [post_text(post)[:4000] for post in posts]
    try:
        claim_payload = _post_systemone(claim_batch_body(texts))
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return [None] * len(posts), _meter_input_tokens() - before
    model, scores = parse_claim_batch(claim_payload, len(posts))
    decisions: list[dict | None] = []
    claim_indexes: list[int] = []
    for index, score in enumerate(scores):
        if score is None:
            decisions.append(None)
            continue
        is_claim = score >= CLAIM_THRESHOLD
        decisions.append(
            {
                "spam_score": None,
                "claim_score": score,
                "section": "",
                "section_confidence": None,
                "is_claim": is_claim,
                "model": model,
            }
        )
        if is_claim:
            claim_indexes.append(index)
    used = _meter_input_tokens() - before
    if not claim_indexes:
        return decisions, used
    stage2 = ASSUMED_BATCH_OVERHEAD + ASSUMED_STAGE2_TOKENS_PER_CLAIM * len(claim_indexes)
    if call_would_exceed(spent + jev_cost_usd(used), stage2, cap):
        return decisions, used
    before_section = _meter_input_tokens()
    try:
        section_payload = _post_systemone(section_batch_body([texts[index] for index in claim_indexes]))
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return decisions, _meter_input_tokens() - before
    _model, sections = parse_section_batch(section_payload, len(claim_indexes))
    for offset, index in enumerate(claim_indexes):
        parsed = sections[offset] if offset < len(sections) else None
        current = decisions[index]
        if parsed is None or not isinstance(current, dict):
            decisions[index] = None
            continue
        choice, confidence = parsed
        current["section"] = choice
        current["section_confidence"] = confidence
        if _model:
            current["model"] = _model
    return decisions, used + (_meter_input_tokens() - before_section)


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
        stage1_estimate = ASSUMED_BATCH_OVERHEAD + ASSUMED_STAGE1_TOKENS_PER_POST * len(comparable)
        if call_would_exceed(spent, stage1_estimate, limit):
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
    usable = [post for post in posts if post_text(post)]
    if count > 0:
        usable = usable[-count:]
    return usable


def format_report(report: dict[str, object]) -> str:
    def pct(value: object) -> str:
        return f"{(Decimal(str(value)) * 100):.1f}%"

    def money(value: object) -> str:
        return f"${Decimal(str(value)):.6f}"

    lines = [
        f"Posts scored both ways: {report['posts_both_ways']}",
        f"Spend: {money(report['spent_usd'])} of {money(report['cap_usd'])} cap",
        (
            f"Per-post: {report['per_post_calls']} calls, "
            f"{report['per_post_input_tokens']} input tokens, "
            f"{money(report['per_post_usd'])} total, "
            f"{money(report['per_post_usd_per_post'])} per post, "
            f"{report['per_post_tokens_per_post']} tokens per post"
        ),
        (
            f"Batched: {report['batch_calls']} calls, "
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
            f"Section agreement: {pct(report['section_agreement'])} "
            f"(bar {pct(report['section_bar'])}) {'PASS' if report['section_pass'] else 'FAIL'}"
        ),
        (
            f"Claims lost: {pct(report['claims_lost'])} "
            f"({report['claims_lost_count']} of {report['per_post_claims']}; "
            f"bar {pct(report['lost_bar'])}) {'PASS' if report['lost_pass'] else 'FAIL'}"
        ),
        (
            f"Per-post spam that the batch still called a claim: "
            f"{report['spam_still_claims']} of {report['spam_posts']} "
            f"(spam is folded into the claim question, so this is not a separate spam score)"
        ),
        f"Failures left out of the rates: {report['failures']}",
        f"Stopped before the requested posts were all scored: {report['stopped_early']}",
        f"Claim threshold {CLAIM_THRESHOLD}, spam threshold {SPAM_THRESHOLD}, batch size {BATCH_SIZE}.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow-test batched Jev against one call per post")
    parser.add_argument("--db", type=Path, default=None, help="Retained corpus SQLite path")
    parser.add_argument("--json", type=Path, default=None, help="JSON list of posts")
    parser.add_argument("--posts", type=int, default=40, help="How many posts to try (newest first)")
    parser.add_argument(
        "--max-spend",
        type=Decimal,
        default=MAX_SPEND_USD,
        help="Dollar cap. Values above 0.03 are clamped.",
    )
    args = parser.parse_args(argv)
    key = (__import__("os").getenv("TYPESAFE_API_KEY") or "").strip()
    if not key:
        print("TYPESAFE_API_KEY is unset. Not calling TypeSafe. Set the key and rerun this script.", file=sys.stderr)
        print("Hard spend cap: $0.03. Example: python scripts/jev_shadow_test.py --db pipeline/data/live_corpus.db --posts 40")
        return 2
    from pipeline.costs import reset_meter

    reset_meter()
    posts = _load_posts(args.db, args.json, args.posts)
    if not posts:
        print("No posts to score.", file=sys.stderr)
        return 1
    report = run_shadow(posts, cap=args.max_spend)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
