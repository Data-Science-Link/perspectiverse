"""Verdict cache, free pre-filter, and the switched-off batch request."""

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from pipeline.costs import (
    JEV_BATCH_SPAM_CLAIM_TOKENS_PER_POST,
    JEV_PLANET_SECTION_TOKENS,
    JEV_PLANETS_PER_DAY,
    SERVICE_DEEPINFRA,
    SERVICE_JEV,
    get_meter,
    jev_cost_usd,
    jev_filter_counts,
    measured_window_projection_line,
    note_jev_cache_hits,
    note_jev_cache_lookups,
    note_jev_prefilter,
    project_jev_daily_usd,
    project_measured_daily_usd,
    record_attempt,
    reset_meter,
    write_cost_run,
)
from pipeline.jev import apply_jev, per_post_body, planet_section_body, reset_jev_state, spam_claim_batch_body
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


def test_retained_corpus_section_counts_as_dedup_skip_on_second_run(monkeypatch, tmp_path):
    """Production reloads claims with section set; the next run must not call Jev."""
    _enable(monkeypatch)
    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        return _answer(0.1, "Politics", claim=0.91, tokens=630)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    moment = datetime(2026, 10, 8, tzinfo=timezone.utc)
    posts = [
        _post("at://claim", "Congress should publish the mail ballot rules before November."),
    ]
    connection = connect(tmp_path / "corpus.db")
    first = apply_jev(posts, connection=connection, now=moment)
    assert calls["n"] == 1
    replace_posts(connection, [post for post in first if post.get("is_claim") is True])
    reset_meter()
    reset_jev_state()
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    reloaded = load_posts(connection)
    assert reloaded[0]["section"] == "Politics"
    second = apply_jev(reloaded, connection=connection, now=moment)
    assert calls["n"] == 1
    assert second == reloaded
    counts = jev_filter_counts()
    assert counts["cache_hits"] == 0
    assert counts["dedup_skips"] == 1
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


def test_batch_request_asks_spam_and_claim_and_not_section(monkeypatch, tmp_path):
    _enable(monkeypatch)
    seen = []

    def fake(url, **kwargs):
        body = json.loads(kwargs["data"].decode("utf-8"))
        seen.append(body)
        encoded = kwargs["data"].decode("utf-8")
        assert "International conflict" not in encoded
        assert "section" not in body["questions"]
        assert "sections" not in body["state"]
        assert body["state"]["spam_true"]
        assert body["state"]["claim_true"]
        assert list(body["questions"]) == ["p0", "c0", "p1", "c1"]
        assert encoded.count(body["state"]["spam_true"]) == 1
        return {
            "model": "jev-1.13.0",
            "answers": {
                "p0": {"type": "noul", "noul": 0.05},
                "c0": {"type": "noul", "noul": 0.91},
                "p1": {"type": "noul", "noul": 0.04},
                "c1": {"type": "noul", "noul": 0.08},
            },
            "usage": {"input_tokens": 410, "output_tokens": 12},
        }

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    claim = _post("at://claim", "Congress should publish the mail ballot rules before November.")
    aside = _post("at://aside", "The Phillies bullpen was worthless again and I cannot watch.")
    connection = connect(tmp_path / "corpus.db")
    kept = apply_jev([claim, aside], connection=connection, batch=True)
    assert len(seen) == 1
    assert [post["uri"] for post in kept if post.get("is_claim") is True] == ["at://claim"]
    assert not kept[0].get("section")
    by_uri = {post["uri"]: post for post in kept}
    assert by_uri["at://aside"]["is_claim"] is False
    tokens = [attempt.input_tokens for attempt in get_meter().attempts()]
    assert tokens == [410]
    stored = connection.execute(
        "SELECT uri, section, spam_score, claim_score FROM jev_verdicts ORDER BY uri"
    ).fetchall()
    assert stored == [("at://aside", None, 0.04, 0.08), ("at://claim", None, 0.05, 0.91)]
    planet = planet_section_body("States should publish the rules.", "Voters need them before November.")
    assert list(planet["questions"]) == ["section"]
    assert planet["state"]["sections"]["World"].startswith("International")
    sample = spam_claim_batch_body(["one post"])
    assert "section" not in sample["questions"]
    connection.close()


def test_filter_counts_are_in_the_run_output_and_tokens_stay_real(tmp_path, capsys):
    reset_meter()
    note_jev_cache_hits(4)
    note_jev_cache_lookups(4)
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
    assert payload["jev_cache_lookups"] == 4
    assert payload["jev_prefilter_skips"] == {"short": 0, "language": 2, "link": 0, "duplicate": 0}
    assert payload["rows"][0]["input_tokens"] == "612"
    assert payload["rows"][0]["calls"] == "1"
    logged = capsys.readouterr().out
    assert "4 cache hits" in logged
    assert "Jev cache: hits 4 / lookups 4 (100%), paid calls 1, est cost $0.0000257" in logged
    assert "0 dedup skips" in logged
    assert "language 2" in logged
    assert "612" in path.read_text(encoding="utf-8")


def test_projection_uses_the_issue_token_assumptions():
    phases_12_10k = project_jev_daily_usd(10_000)
    phases_12_100k = project_jev_daily_usd(100_000)
    batched_10k = project_jev_daily_usd(10_000, batched=True)
    batched_100k = project_jev_daily_usd(100_000, batched=True)
    assert phases_12_100k.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal("1.03")
    assert phases_12_10k * 10 == phases_12_100k
    assert JEV_BATCH_SPAM_CLAIM_TOKENS_PER_POST == 103
    assert JEV_PLANET_SECTION_TOKENS == 490
    assert JEV_PLANETS_PER_DAY == 300
    assert batched_100k.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) == Decimal("0.182745")
    assert batched_10k.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) == Decimal("0.023831")
    assert batched_10k * 10 != batched_100k
    assert jev_cost_usd(1_000_000) == Decimal("0.042")


def test_oct_16_steady_day_projects_100k_at_or_under_half_dollar():
    """Run 38894377011. The new-post quota scales. The cache hit rate does not.

    Ledger: 9,985 posts, 1,362 paid Jev calls, Jev $0.03808182, labeling $0.11712596.
    Hits were 2/1,364. A 45% discount is not applied.
    """
    jev = Decimal("0.03808182")
    label = Decimal("0.11712596")
    projected = project_measured_daily_usd(
        measured_posts=9985,
        jev_usd=jev,
        label_usd=label,
        jev_calls=1362,
    )
    assert projected["topup"] is False
    assert projected["total_usd"] == projected["jev_usd"] + label
    assert projected["jev_usd"] == jev * projected["scale"]
    assert projected["total_usd"] <= Decimal("0.50")
    assert projected["total_usd"] > Decimal("0.49")
    # The same dollars with the observed 0.1% hits, or with the rejected 45% assumption.
    again = project_measured_daily_usd(
        measured_posts=9985,
        jev_usd=jev,
        label_usd=label,
        jev_calls=1362,
    )
    assert again["total_usd"] == projected["total_usd"]
    assert projected["total_usd"] != (jev * projected["scale"] * Decimal("0.55")) + label


def test_oct_15_shortfall_is_not_a_steady_100k_day():
    """Run 38677894812 paid 10,230 Jev calls to refill a short corpus."""
    projected = project_measured_daily_usd(
        measured_posts=9688,
        jev_usd=Decimal("0.28440674"),
        label_usd=Decimal("0.11022006"),
        jev_calls=10230,
    )
    assert projected["topup"] is True
    assert projected["total_usd"] > Decimal("0.50")


def test_projection_line_names_the_quota_and_skips_a_relabel(tmp_path, capsys):
    reset_meter()
    line = measured_window_projection_line(measured_posts=9985, attempts=())
    assert line == "Jev 100K projection: not this run (no paid Jev calls on a scored window)."
    note_jev_cache_hits(2)
    note_jev_cache_lookups(1364)
    record_attempt(
        service=SERVICE_JEV,
        model="jev-1.13.0",
        input_tokens=906710,
        output_tokens=0,
        cost_usd=Decimal("0.03808182"),
        cost_source="computed",
        status="success",
    )
    record_attempt(
        service=SERVICE_DEEPINFRA,
        model="meta-llama/Llama-3.3-70B",
        input_tokens=717730,
        output_tokens=1000,
        cost_usd=Decimal("0.11712596"),
        cost_source="reported",
        status="success",
    )
    path = write_cost_run(
        posts_processed=9985,
        planets_published=110,
        started_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
        path=tmp_path / "cost_run.json",
    )
    assert path is not None
    logged = capsys.readouterr().out
    assert "steady new-post quota" in logged
    assert "Jev 100K projection:" in logged
    total_text = logged.split("Jev 100K projection: $", 1)[1].split("/day", 1)[0]
    assert Decimal(total_text) <= Decimal("0.50")


def test_corrupt_verdict_is_warned_and_rescored(monkeypatch, tmp_path, capsys):
    """A bad spam_score fails the cache read open. The post is scored, not dropped."""
    _enable(monkeypatch)
    from pipeline.jev import jev_cache_version

    connection = connect(tmp_path / "corpus.db")
    connection.execute(
        """
        INSERT INTO jev_verdicts (
            uri, spam_score, claim_score, section, model, scored_on, text_fp, cache_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("at://claim", "not-a-score", 0.2, "", "jev-1.13.0", "2026-10-08", "", jev_cache_version()),
    )
    connection.commit()
    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        return _answer(0.1, "Politics", claim=0.91, tokens=600)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    text = "Congress should publish the mail ballot rules before November."
    kept = apply_jev(
        [_post("at://claim", text)],
        connection=connection,
        now=datetime(2026, 10, 8, tzinfo=timezone.utc),
    )
    err = capsys.readouterr().err
    assert "WARNING: Jev verdict cache was not read" in err
    assert calls["n"] == 1
    assert [post["uri"] for post in kept] == ["at://claim"]
    assert kept[0]["is_claim"] is True
    assert kept[0]["section"] == "Politics"
    connection.close()


def test_same_text_under_a_new_uri_reuses_the_verdict(monkeypatch, tmp_path):
    """A day-later copy is a cache hit, not a second paid call and not a drop."""
    _enable(monkeypatch)
    calls = {"n": 0}

    def fake(url, **kwargs):
        del url, kwargs
        calls["n"] += 1
        return _answer(0.1, "Politics", claim=0.91, tokens=600)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    text = "Congress should publish the mail ballot rules before November."
    moment = datetime(2026, 10, 11, tzinfo=timezone.utc)
    database = tmp_path / "corpus.db"
    connection = connect(database)
    first = apply_jev([_post("at://day-one", text)], connection=connection, now=moment)
    connection.close()
    assert calls["n"] == 1
    assert first[0]["section"] == "Politics"
    reset_meter()
    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    later = connect(database)
    second = apply_jev(
        [_post("at://day-two", text)],
        connection=later,
        now=datetime(2026, 10, 12, tzinfo=timezone.utc),
    )
    later.close()
    assert calls["n"] == 1
    assert second[0]["uri"] == "at://day-two"
    assert second[0]["is_claim"] is True
    assert second[0]["section"] == "Politics"
    assert jev_filter_counts()["cache_hits"] == 1
    assert jev_filter_counts()["lookups"] == 1
    assert jev_filter_counts()["duplicate"] == 0
    stored = connect(database)
    rows = stored.execute("SELECT uri FROM jev_verdicts ORDER BY uri").fetchall()
    stored.close()
    assert [row[0] for row in rows] == ["at://day-one", "at://day-two"]


def test_cache_file_warms_a_fresh_database(monkeypatch, tmp_path):
    _enable(monkeypatch)
    monkeypatch.setenv("JEV_VERDICT_CACHE", str(tmp_path / "jev_verdict_cache.sqlite"))
    calls = {"n": 0}

    def fake(url, **kwargs):
        del url, kwargs
        calls["n"] += 1
        return _answer(0.1, "World", claim=0.9, tokens=600)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    text = "Hospitals need more nurses before the winter flu season begins again."
    first_db = connect(tmp_path / "one.db")
    apply_jev([_post("at://kept", text)], connection=first_db, now=datetime(2026, 10, 12, tzinfo=timezone.utc))
    first_db.close()
    assert (tmp_path / "jev_verdict_cache.sqlite").is_file()
    reset_meter()
    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    fresh = connect(tmp_path / "two.db")
    kept = apply_jev([_post("at://kept", text)], connection=fresh, now=datetime(2026, 10, 12, tzinfo=timezone.utc))
    fresh.close()
    assert calls["n"] == 1
    assert kept[0]["section"] == "World"
    assert jev_filter_counts()["cache_hits"] == 1
    assert jev_filter_counts()["lookups"] == 1


def test_cache_bound_drops_the_oldest_rows(tmp_path):
    from pipeline.jev_cache import enforce_jev_cache_bound, export_persistent_cache

    connection = connect(tmp_path / "corpus.db")
    save_jev_verdicts(
        connection,
        [
            ("at://d1", 0.1, 0.9, "World", "jev-1.13.0", "2026-10-01", "a" * 16),
            ("at://d2", 0.1, 0.9, "World", "jev-1.13.0", "2026-10-02", "b" * 16),
            ("at://d3", 0.1, 0.9, "World", "jev-1.13.0", "2026-10-03", "c" * 16),
            ("at://d4", 0.1, 0.9, "World", "jev-1.13.0", "2026-10-04", "d" * 16),
            ("at://d5", 0.1, 0.9, "World", "jev-1.13.0", "2026-10-05", "e" * 16),
        ],
    )
    removed = enforce_jev_cache_bound(connection, max_rows=2)
    assert removed == 3
    left = connection.execute("SELECT uri FROM jev_verdicts ORDER BY uri").fetchall()
    assert [row[0] for row in left] == ["at://d4", "at://d5"]
    blob = tmp_path / "cache.sqlite"
    # Long fingerprints so the snapshot is larger than the byte cap.
    save_jev_verdicts(
        connection,
        [
            (
                f"at://extra/{index}",
                0.1,
                0.9,
                "Politics",
                "jev-1.13.0",
                "2026-10-08",
                f"{index:064x}",
            )
            for index in range(800)
        ],
    )
    export_persistent_cache(connection, blob, max_rows=5_000, max_bytes=24_000)
    assert blob.is_file()
    assert blob.stat().st_size <= 24_000
    surviving = connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0]
    assert surviving < 802
    connection.close()


def test_morning_fetch_counts_a_cached_uri_as_a_hit(monkeypatch, tmp_path):
    from pipeline.live import _collect_posts

    connection = connect(tmp_path / "corpus.db")
    from pipeline.jev import jev_cache_version

    save_jev_verdicts(
        connection,
        [("at://cached", 0.1, 0.2, "Other", "jev-1.13.0", "2026-10-12", "f" * 16, jev_cache_version())],
    )
    seen = {"calls": []}

    def fake_extract(**kwargs):
        cache_uris = set(kwargs.get("cache_uris") or ())
        skip_uris = set(kwargs.get("skip_uris") or ())
        seen["calls"].append((cache_uris, skip_uris))
        reused = kwargs.get("cache_reused")
        if reused is not None and "at://cached" in cache_uris:
            reused.add("at://cached")
        return [
            {
                "uri": "at://fresh",
                "author": "new",
                "text": "People were arguing about the rent increase on my block again today.",
                "likes": 2,
                "created_at": "2026-10-12T12:00:00Z",
            }
        ]

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    reset_meter()
    _collect_posts(
        [],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 10, 12, tzinfo=timezone.utc),
    )
    connection.close()
    assert seen["calls"]
    assert any("at://cached" in cache_uris and "at://cached" in skip_uris for cache_uris, skip_uris in seen["calls"])
    assert jev_filter_counts()["cache_hits"] == 1
    assert jev_filter_counts()["lookups"] == 1


def test_model_or_prompt_change_invalidates_the_cached_verdict(monkeypatch, tmp_path):
    """A different model name, or different question wording, is scored again."""
    from pipeline.jev import jev_cache_version, known_scored_uris

    _enable(monkeypatch)
    calls = {"n": 0}

    def fake(url, **kwargs):
        del url, kwargs
        calls["n"] += 1
        return _answer(0.1, "Politics", claim=0.91, tokens=600)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    text = "Congress should publish the mail ballot rules before November."
    moment = datetime(2026, 10, 12, tzinfo=timezone.utc)
    connection = connect(tmp_path / "corpus.db")
    original = jev_cache_version()
    apply_jev([_post("at://one", text)], connection=connection, now=moment)
    assert calls["n"] == 1
    stored = connection.execute(
        "SELECT cache_version FROM jev_verdicts WHERE uri = 'at://one'"
    ).fetchone()
    assert stored[0] == original
    assert original.startswith("jev-latest:")

    reset_meter()
    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    apply_jev([_post("at://two", text)], connection=connection, now=moment)
    assert calls["n"] == 1
    assert jev_filter_counts()["cache_hits"] == 1

    monkeypatch.setenv("JEV_MODEL", "jev-other")
    changed = jev_cache_version()
    assert changed != original
    assert known_scored_uris(connection, now=moment) == set()
    reset_meter()
    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    apply_jev([_post("at://one", text)], connection=connection, now=moment)
    assert calls["n"] == 2
    assert jev_filter_counts()["cache_hits"] == 0

    monkeypatch.delenv("JEV_MODEL", raising=False)
    monkeypatch.setattr(
        "pipeline.jev.SPAM_TRUE",
        "Promo, bot, giveaway, follow-bait, or an advertisement, including a coupon",
    )
    assert jev_cache_version() != original
    assert jev_cache_version() != changed
    reset_meter()
    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    apply_jev([_post("at://three", text)], connection=connection, now=moment)
    assert calls["n"] == 3
    assert jev_filter_counts()["cache_hits"] == 0
    connection.close()


def test_replay_second_run_hits_and_pays_nothing(tmp_path):
    from pipeline.jev_cache import replay_same_posts

    report = replay_same_posts(tmp_path)
    assert report["run1"]["http_calls"] == report["posts"]
    assert report["run1"]["paid_calls"] == report["posts"]
    assert report["run1"]["hits"] == 0
    assert report["run1"]["lookups"] == report["posts"]
    assert report["run2"]["http_calls"] == 0
    assert report["run2"]["paid_calls"] == 0
    assert report["run2"]["hits"] == report["posts"]
    assert report["run2"]["lookups"] == report["posts"]
    assert report["run2"]["cost_usd"] == "0"
    assert report["run2"]["line"] == (
        f"Jev cache: hits {report['posts']} / lookups {report['posts']} (100%), "
        "paid calls 0, est cost $0.00"
    )
    assert report["file_only"]["paid_calls"] == 0
    assert report["file_only"]["hits"] == report["posts"]
    assert "Jev cache: hits 0 / lookups" in report["run1"]["line"]
    assert "paid calls 4" in report["run1"]["line"]


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
