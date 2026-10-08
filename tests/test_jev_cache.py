"""Verdict cache, free pre-filter, and the switched-off batch request."""

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from pipeline.costs import (
    format_jev_filters,
    get_meter,
    jev_cost_usd,
    jev_filter_counts,
    note_jev_cache_hits,
    note_jev_prefilter,
    project_jev_daily_usd,
    reset_meter,
    write_cost_run,
)
from pipeline.jev import apply_jev, claim_batch_body, per_post_body, reset_jev_state, section_batch_body
from pipeline.jev_prefilter import MIN_WORDS, measure_claim_loss, prefilter_reason, DuplicateIndex
from pipeline.settings import DEFAULTS
from pipeline.store import (
    JEV_VERDICT_TTL_DAYS,
    connect,
    expire_jev_verdicts,
    load_posts,
    replace_posts,
    save_jev_verdicts,
)


def _post(uri: str, text: str, **extra) -> dict:
    post = {
        "uri": uri,
        "author": "ada",
        "text": text,
        "clean_text": text,
        "likes": 1,
        "created_at": "2026-10-07T00:00:00Z",
    }
    post.update(extra)
    return post


def _answer(spam: float, section: str = "World", claim: float | None = 0.9, tokens: int = 600) -> dict:
    answers = {
        "spam": {"type": "noul", "noul": spam},
        "section": {
            "type": "choice",
            "choice": section,
            "confidence": 0.74,
            "probabilities": {section: 0.74, "Other": 0.26},
        },
    }
    if claim is not None:
        answers["claim"] = {"type": "noul", "noul": claim}
    return {
        "model": "jev-1.13.0",
        "answers": answers,
        "usage": {"input_tokens": tokens, "output_tokens": 20},
    }


def _enable(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_jev_state()
    reset_meter()


def test_batching_defaults_off():
    assert DEFAULTS["jev_batch"] is False
    assert MIN_WORDS == 6
    assert JEV_VERDICT_TTL_DAYS == 14


def test_per_post_prompt_is_unchanged():
    body = per_post_body("Congress should publish the mail ballot rules before November.")
    assert isinstance(body["state"], str)
    assert set(body["questions"]) == {"spam", "section", "claim"}
    assert "International conflict" in body["questions"]["section"]["criteria"]["World"]


def test_uri_is_not_scored_twice_including_nonclaims_and_spam(monkeypatch, tmp_path):
    _enable(monkeypatch)
    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        state = json.loads(kwargs["data"].decode("utf-8"))["state"]
        assert isinstance(state, str)
        if "giveaway" in state:
            return _answer(0.95, "Other", claim=0.1, tokens=610)
        if "Phillies" in state:
            return _answer(0.1, "Sports", claim=0.08, tokens=620)
        return _answer(0.1, "Politics", claim=0.91, tokens=630)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    moment = datetime(2026, 10, 8, tzinfo=timezone.utc)
    posts = [
        _post("at://spam", "Join my crypto giveaway and follow back right now please"),
        _post("at://aside", "The Phillies bullpen was worthless again and I cannot watch."),
        _post("at://claim", "Congress should publish the mail ballot rules before November."),
    ]
    connection = connect(tmp_path / "corpus.db")
    first = apply_jev(posts, connection=connection, now=moment)
    second = apply_jev(posts, connection=connection, now=moment)
    assert calls["n"] == 3
    by_uri = {post["uri"]: post for post in first}
    assert "at://spam" not in by_uri
    assert by_uri["at://aside"]["is_claim"] is False
    assert by_uri["at://claim"]["is_claim"] is True
    assert by_uri["at://claim"]["section"] == "Politics"
    cached = connection.execute(
        "SELECT uri, spam_score, claim_score, section, model, scored_on FROM jev_verdicts ORDER BY uri"
    ).fetchall()
    assert [row[0] for row in cached] == ["at://aside", "at://claim", "at://spam"]
    assert cached[0][2] == 0.08
    assert cached[2][1] == 0.95
    assert all(row[4] == "jev-1.13.0" and row[5] == "2026-10-08" for row in cached)
    assert {post["uri"] for post in second if post.get("is_claim") is True} == {"at://claim"}
    assert jev_filter_counts()["cache_hits"] == 3
    attempts = get_meter().attempts()
    assert sorted(attempt.input_tokens for attempt in attempts) == [610, 620, 630]
    connection.close()


def test_prefilter_skips_are_not_calls_and_not_cached(monkeypatch, tmp_path):
    _enable(monkeypatch)
    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        return _answer(0.1, "World", claim=0.9, tokens=640)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    dutch = "Het gaat van kwaad naar erger en iedereen moet zwijgen over de moordende terreur van het regime vandaag."
    headline = "Ukraine’s Surprise Counterattack Sets Back Putin’s Donbas Goals"
    posts = [
        _post("at://short", "Pay for his crimes now"),
        _post("at://link", "https://example.com/only-a-link"),
        _post("at://nl", dutch),
        _post("at://langs", "Congress should publish the mail ballot rules before November.", langs=["nl"]),
        _post("at://headline", headline),
        _post("at://copy", headline),
    ]
    connection = connect(tmp_path / "corpus.db")
    kept = apply_jev(posts, connection=connection, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
    assert calls["n"] == 1
    assert [post["uri"] for post in kept] == ["at://headline"]
    stored = {row[0] for row in connection.execute("SELECT uri FROM jev_verdicts")}
    assert stored == {"at://headline"}
    counts = jev_filter_counts()
    assert counts["short"] == 1
    assert counts["link"] == 1
    assert counts["language"] == 2
    assert counts["duplicate"] == 1
    assert word_floor_keeps_a_seven_word_claim()
    connection.close()


def word_floor_keeps_a_seven_word_claim() -> bool:
    seven = _post("at://seven", "Kevin Knight must pay for his crimes")
    five = _post("at://five", "Pay for his crimes now")
    assert len(seven["clean_text"].split()) == 7
    assert prefilter_reason(seven, DuplicateIndex()) is None
    assert prefilter_reason(five, DuplicateIndex()) == "short"
    return True


def test_verdicts_expire_after_14_days_and_survive_post_replacement(tmp_path):
    connection = connect(tmp_path / "corpus.db")
    save_jev_verdicts(
        connection,
        [
            ("at://old", 0.1, 0.2, "World", "jev-1.13.0", "2026-09-23", "abc"),
            ("at://edge", 0.1, 0.9, "Politics", "jev-1.13.0", "2026-09-24", "def"),
        ],
    )
    removed = expire_jev_verdicts(connection, "2026-10-08")
    assert removed == 1
    left = connection.execute("SELECT uri FROM jev_verdicts").fetchall()
    assert left == [("at://edge",)]
    replace_posts(
        connection,
        [
            {
                "uri": "at://edge",
                "author": "ada",
                "text": "A claim that stays in the post table.",
                "clean_text": "A claim that stays in the post table.",
                "likes": 1,
                "created_at": "2026-10-01T00:00:00Z",
                "section": "Politics",
                "section_confidence": 0.5,
                "spam_score": 0.1,
                "is_claim": True,
            }
        ],
    )
    assert load_posts(connection)[0]["uri"] == "at://edge"
    assert connection.execute("SELECT uri FROM jev_verdicts").fetchall() == [("at://edge",)]
    connection.close()


def test_verdict_rows_stay_small(tmp_path):
    path = tmp_path / "corpus.db"
    connection = connect(path)
    connection.commit()
    before = path.stat().st_size
    rows = [
        (
            f"at://did:plc:222p42fegwhwfyrc3gqam76j/app.bsky.feed.post/{index:013d}",
            0.12,
            0.83,
            "Politics",
            "jev-1.13.0",
            "2026-10-08",
            f"{index:016x}",
        )
        for index in range(1000)
    ]
    save_jev_verdicts(connection, rows)
    connection.close()
    per_row = (path.stat().st_size - before) / 1000
    assert per_row < 400


def test_batch_request_sends_definitions_once_and_sections_only_for_claims(monkeypatch):
    _enable(monkeypatch)
    seen = []

    def fake(url, **kwargs):
        body = json.loads(kwargs["data"].decode("utf-8"))
        seen.append(body)
        state = body["state"]
        if "claim_true" in state:
            assert "spam" not in body["questions"]
            assert "section" not in body["questions"]
            assert "advertisement" in state["claim_false"]
            return {
                "model": "jev-1.13.0",
                "answers": {"c0": {"type": "noul", "noul": 0.91}, "c1": {"type": "noul", "noul": 0.08}},
                "usage": {"input_tokens": 410, "output_tokens": 12},
            }
        assert "sections" in state
        encoded = kwargs["data"].decode("utf-8")
        assert encoded.count("International conflict") == 1
        assert state["posts"] == ["Congress should publish the mail ballot rules before November."]
        return {
            "model": "jev-1.13.0",
            "answers": {
                "s0": {"type": "choice", "choice": "Politics", "confidence": 0.8, "probabilities": {"Politics": 0.8}}
            },
            "usage": {"input_tokens": 250, "output_tokens": 8},
        }

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    claim = _post("at://claim", "Congress should publish the mail ballot rules before November.")
    aside = _post("at://aside", "The Phillies bullpen was worthless again and I cannot watch.")
    kept = apply_jev([claim, aside], batch=True)
    assert len(seen) == 2
    assert [post["uri"] for post in kept if post.get("is_claim") is True] == ["at://claim"]
    assert kept[0]["section"] == "Politics"
    by_uri = {post["uri"]: post for post in kept}
    assert by_uri["at://aside"]["is_claim"] is False
    tokens = sorted(attempt.input_tokens for attempt in get_meter().attempts())
    assert tokens == [250, 410]
    sample = section_batch_body(["one post", "two post"])
    assert list(sample["questions"]) == ["s0", "s1"]


def test_filter_counts_are_in_the_run_output_and_tokens_stay_real(tmp_path, capsys):
    reset_meter()
    note_jev_cache_hits(4)
    note_jev_prefilter("language", 2)
    from pipeline.costs import record_jev_attempt

    record_jev_attempt(
        requested_model="jev-latest",
        payload={"model": "jev-1.13.0", "usage": {"input_tokens": 612, "output_tokens": 18}},
        status="success",
    )
    path = tmp_path / "cost_run.json"
    write_cost_run(
        posts_processed=10,
        planets_published=1,
        started_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        path=path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["jev_cache_hits"] == 4
    assert payload["jev_prefilter_skips"] == {"short": 0, "language": 2, "link": 0, "duplicate": 0}
    assert payload["rows"][0]["input_tokens"] == "612"
    assert payload["rows"][0]["calls"] == "1"
    logged = capsys.readouterr().out
    assert "4 cache hits" in logged
    assert "language 2" in logged
    assert "612" in path.read_text(encoding="utf-8")


def test_projection_uses_the_issue_token_assumptions():
    phases_12_10k = project_jev_daily_usd(10_000)
    phases_12_100k = project_jev_daily_usd(100_000)
    phase3_10k = project_jev_daily_usd(10_000, phase3=True)
    phase3_100k = project_jev_daily_usd(100_000, phase3=True)
    assert phases_12_100k.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal("1.03")
    assert phase3_100k.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal("0.19")
    assert phases_12_10k * 10 == phases_12_100k
    assert phase3_10k * 10 == phase3_100k
    assert jev_cost_usd(1_000_000) == Decimal("0.042")


def test_measure_claim_loss_counts_each_post_once():
    posts = [
        _post("at://a", "Pay for his crimes now"),
        _post("at://b", "Congress should publish the mail ballot rules before November."),
        _post("at://c", "Congress should publish the mail ballot rules before November."),
    ]
    counts = measure_claim_loss(posts)
    assert counts["short"] == 1
    assert counts["duplicate"] == 1
    assert counts["kept"] == 1
    assert counts["dropped"] == 2
