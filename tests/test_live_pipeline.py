import json
import sqlite3

from pipeline.live import posts_for_planets, publish_volumes, run_live
from pipeline.run_pipeline import main
from pipeline.schema import validate_payload
from tests.corpus import build_tiny_posts


def test_live_fixture_writes_contract(tmp_path):
    fixture = tmp_path / "posts.json"
    fixture.write_text(json.dumps(build_tiny_posts()), encoding="utf-8")
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "\n".join(
            [
                "min_cluster_size: 8",
                "cluster_backend: lexical",
                "label_backend: heuristic",
                "sample_size: 200",
                "window_hours: 168",
                "representative_posts: 12",
                "seed: 0",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "data.json"
    database = tmp_path / "posts.db"
    main(
        [
            "--live",
            "--fixture",
            str(fixture),
            "--config",
            str(config),
            "--output",
            str(output),
            "--db",
            str(database),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    validate_payload(payload)
    assert payload["mode"] == "live"
    assert payload["source"] == "fixture"
    assert payload["total_posts"] == len(build_tiny_posts())
    connection = sqlite3.connect(database)
    post_count = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    topic_count = connection.execute("SELECT COUNT(DISTINCT topic_id) FROM topic_membership").fetchone()[0]
    connection.close()
    assert post_count == len(build_tiny_posts())
    assert topic_count == 10
    assert all(len(topic["perspectives"][0].get("arguments") or []) >= 2 for topic in payload["topics"])
    assert all(topic["name"] for topic in payload["topics"])
    assert all(topic.get("brief") and topic.get("detail") for topic in payload["topics"])
    assert all(topic.get("post_count", 0) > 0 for topic in payload["topics"])
    assert all(
        sum(face.get("post_count", 0) for face in topic["perspectives"]) == topic["post_count"]
        for topic in payload["topics"]
    )
    for topic in payload["topics"]:
        for face in topic["perspectives"]:
            shown = face["representative_posts"]
            assert shown
            assert all(post.get("match") is not None for post in shown)
            matches = [post["match"] for post in shown]
            assert matches == sorted(matches, reverse=True)
    assert payload["digest"]["planets"]
    assert payload["digest"]["planets"][0]["disagreement"]


def test_an_ungrounded_and_tail_is_removed():
    from pipeline.live import _without_ungrounded_tail

    posts = [{"text": "Rape culture is definitely on the rise and people stay silent."}]
    assert _without_ungrounded_tail("Rape culture exists and is understudied", posts) == "Rape culture exists"
    iran = [{"text": "The US may strike Iran and Iran may widen the conflict."}]
    assert _without_ungrounded_tail("US and Iran may engage in conflict", iran) == "US and Iran may engage in conflict"
    artists = [{"text": "AI harms artists and creative workers."}]
    assert _without_ungrounded_tail("AI harms artists and creatives", artists) == "AI harms artists and creatives"


def test_a_title_has_to_cover_most_of_its_posts():
    from pipeline.live import _title_covers_posts

    outrage = [
        {"text": "Social media posts spark outrage and generate debate about discrimination."},
        {"text": "People are furious about a trans man in the Odyssey and the casting."},
        {"text": "The grooming meme treats misconduct allegations like a fandom war."},
    ]
    artists = [
        {"text": "Stop spreading AI-generated slop. Small artists cannot thrive."},
        {"text": "Artists do get it. Artists love new tools that are not generative slop."},
        {"text": "AI ripped the passion out of my writing."},
    ]
    assert not _title_covers_posts("Outrage Over Issues", outrage)
    assert _title_covers_posts("Artists Reject AI", artists)


def test_planet_name_must_appear_on_a_published_face():
    from pipeline.live import _name_misses_faces

    racism = [
        {
            "title": "Racism Persists",
            "summary": "Racism is present in society.",
            "representative_posts": [
                {"text": "You cannot half-ass destroying racism after this election."},
                {"text": "A society that still refers to Black people as slaves."},
            ],
        }
    ]
    cornell = [
        {
            "title": "Rape Culture",
            "summary": "Rapists are being sympathized with.",
            "representative_posts": [{"text": "Any college fostering rape culture needs to be dismantled."}],
        },
        {
            "title": "Cornell Rape Case",
            "summary": "Trump supports Cornell rape suspects.",
            "representative_posts": [{"text": "Trump was asked about the Cornell rape case."}],
        },
    ]
    assert _name_misses_faces("Black Lives", racism)
    assert not _name_misses_faces("Racism Persists", racism)
    assert not _name_misses_faces("Cornell Rape Case", cornell)


def test_title_and_summary_must_share_a_claim_word():
    from pipeline.live import _claim_words_overlap

    assert _claim_words_overlap("Death Penalty", "The death penalty is barbaric.")
    assert _claim_words_overlap("Botched Execution", "The state is inept at legal executions.")
    assert _claim_words_overlap("Rape Culture", "Trump sympathizes with rapists.")
    assert _claim_words_overlap("Artists Reject AI", "AI harms artists and creatives.")
    assert not _claim_words_overlap(
        "Grooming Help",
        "Online discussions prioritize outrage over serious issues.",
    )
    assert not _claim_words_overlap("Rape Culture", "Men are the problem.")


def test_drop_planet_that_admits_no_shared_claim():
    from pipeline.live import _drop_unshared_planets, _renumber_planets

    mixed = {
        "id": 9,
        "name": "Canada",
        "total_volume_percent": 20,
        "perspectives": [{"id": "9A", "title": "Canadian Politics", "summary": "These posts share various issues and opinions."}],
    }
    solid = {
        "id": 10,
        "name": "Taxes",
        "total_volume_percent": 80,
        "perspectives": [{"id": "10A", "title": "Tax the Rich", "summary": "Wealth taxes should fund public services."}],
    }
    kept = _drop_unshared_planets([mixed, solid])
    assert [topic["name"] for topic in kept] == ["Taxes"]
    renumbered, membership, _faces = _renumber_planets(
        kept,
        [("at://gone", 9), ("at://kept", 10)],
        [("at://gone", 9, 0, 0.1), ("at://kept", 10, 0, 0.2)],
    )
    assert renumbered[0]["id"] == 1
    assert renumbered[0]["perspectives"][0]["id"] == "1A"
    assert membership == [("at://kept", 1)]


def test_live_run_refuses_unlabeled_posts():
    posts = [{"uri": "at://a", "is_claim": None, "clean_text": "hello", "text": "hello"}]
    try:
        posts_for_planets(posts, require_claims=True)
    except RuntimeError as exc:
        assert "unlabeled" in str(exc).lower() or "Jev" in str(exc)
    else:
        raise AssertionError("unlabeled posts should not be clustered")
    aside = dict(posts[0], is_claim=False)
    claim = dict(posts[0], uri="at://b", is_claim=True)
    kept = posts_for_planets([posts[0], aside, claim], require_claims=True)
    assert [post["uri"] for post in kept] == ["at://b"]
    assert posts_for_planets(posts, require_claims=False) == posts


def test_run_live_function_matches_cli(tmp_path):
    fixture = tmp_path / "posts.json"
    fixture.write_text(json.dumps(build_tiny_posts()), encoding="utf-8")
    config = tmp_path / "pipeline.yaml"
    config.write_text("min_cluster_size: 8\ncluster_backend: lexical\nlabel_backend: heuristic\nseed: 0\n", encoding="utf-8")
    path = run_live(fixture=fixture, output=tmp_path / "out.json", config=config, db_path=tmp_path / "p.db")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert 2 <= len(payload["topics"][0]["perspectives"]) <= 6
    assert payload["topics"][0]["perspectives"][0]["representative_posts"][0]["likes"] >= 0


def _seed_corpus(database, posts):
    from pipeline.cleaning import clean_posts
    from pipeline.store import connect, replace_posts

    connection = connect(database)
    replace_posts(connection, clean_posts(posts))
    connection.close()


def _heuristic_config(path):
    path.write_text(
        "\n".join(
            [
                "min_cluster_size: 8",
                "cluster_backend: lexical",
                "label_backend: heuristic",
                "sample_size: 200",
                "window_hours: 168",
                "representative_posts: 12",
                "seed: 0",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_relabel_skips_bluesky_and_keeps_the_corpus(monkeypatch, tmp_path):
    posts = build_tiny_posts()
    database = tmp_path / "live_corpus.db"
    _seed_corpus(database, posts)

    def boom(**_kwargs):
        raise AssertionError("relabel must not fetch Bluesky")

    monkeypatch.setattr("pipeline.live.extract_posts", boom)
    output = tmp_path / "data.json"
    main(
        [
            "--live",
            "--relabel",
            "--config",
            str(_heuristic_config(tmp_path / "pipeline.yaml")),
            "--output",
            str(output),
            "--db",
            str(database),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    validate_payload(payload)
    assert payload["mode"] == "live"
    assert payload["source"] == "bluesky"
    assert payload["total_posts"] == len(posts)
    assert len(payload["topics"]) == 10
    connection = sqlite3.connect(database)
    remaining = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    connection.close()
    assert remaining == len(posts)


def test_bluesky_403_does_not_shrink_retained_corpus(monkeypatch, tmp_path):
    posts = build_tiny_posts()
    database = tmp_path / "live_corpus.db"
    _seed_corpus(database, posts)

    def forbidden(**_kwargs):
        raise RuntimeError("HTTP 403 from api.bsky.app")

    monkeypatch.setattr("pipeline.live.extract_posts", forbidden)

    def keep_as_claims(posts):
        return [{**post, "is_claim": True, "section": post.get("section") or "Other"} for post in posts]

    monkeypatch.setattr("pipeline.live.apply_jev", keep_as_claims)
    output = tmp_path / "data.json"
    path = run_live(
        output=output,
        config=_heuristic_config(tmp_path / "pipeline.yaml"),
        db_path=database,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload)
    assert payload["total_posts"] == len(posts)
    connection = sqlite3.connect(database)
    remaining = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    connection.close()
    assert remaining == len(posts)


def test_seeded_corpus_without_ledger_is_not_refilled(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from pipeline.live import _collect_posts
    from pipeline.store import connect, fetched_day_set, replace_posts

    database = tmp_path / "live.db"
    connection = connect(database)
    seeded = {
        "uri": "at://seeded",
        "author": "old",
        "text": "A seeded sports post about the nfl that should survive an empty ledger.",
        "clean_text": "A seeded sports post about the nfl that should survive an empty ledger.",
        "likes": 1,
        "created_at": "2026-09-28T00:00:00Z",
    }
    replace_posts(connection, [seeded])

    def boom(**_kwargs):
        raise AssertionError("posts already stored must not be replaced by a 7-day Bluesky refill")

    monkeypatch.setattr("pipeline.live.extract_posts", boom)
    cleaned, source, refreshed = _collect_posts(
        [seeded],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the", "and"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    assert refreshed is False
    assert source == "bluesky"
    assert [post["uri"] for post in cleaned] == ["at://seeded"]
    assert "2026-09-28" in fetched_day_set(connection)
    connection.close()


def test_empty_corpus_still_refills_seven_days(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from pipeline.live import _collect_posts
    from pipeline.store import connect, fetched_day_set

    connection = connect(tmp_path / "live.db")

    def fake_extract(**kwargs):
        assert kwargs["queries"] == ["the", "and"]
        assert kwargs["window_hours"] == 168
        return [
            {
                "uri": "at://fresh",
                "author": "new",
                "text": "People were arguing about the rent increase on my block again today.",
                "likes": 2,
                "created_at": "2026-09-28T12:00:00Z",
            }
        ]

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    cleaned, source, refreshed = _collect_posts(
        [],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the", "and"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    assert refreshed is True
    assert source == "bluesky"
    assert [post["uri"] for post in cleaned] == ["at://fresh"]
    assert "2026-09-28" in fetched_day_set(connection)
    assert "2026-09-22" in fetched_day_set(connection)
    connection.close()


def test_missing_day_is_a_refresh_not_a_refill(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from pipeline.live import _collect_posts
    from pipeline.store import connect, fetched_day_set, replace_posts

    connection = connect(tmp_path / "live.db")
    seeded = {
        "uri": "at://seeded",
        "author": "old",
        "text": "A seeded post from earlier in the window about rent and housing policy.",
        "clean_text": "A seeded post from earlier in the window about rent and housing policy.",
        "likes": 1,
        "created_at": "2026-09-26T00:00:00Z",
    }
    replace_posts(connection, [seeded])

    def fake_extract(**kwargs):
        assert kwargs["window_hours"] == 24
        return [
            {
                "uri": "at://today",
                "author": "new",
                "text": "Today's argument about the same rent increase on the block.",
                "likes": 2,
                "created_at": "2026-09-28T12:00:00Z",
            }
        ]

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    cleaned, _source, refreshed = _collect_posts(
        [seeded],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    assert refreshed is True
    assert {post["uri"] for post in cleaned} == {"at://seeded", "at://today"}
    assert "2026-09-26" in fetched_day_set(connection)
    assert "2026-09-28" in fetched_day_set(connection)
    connection.close()


def test_recorded_utc_day_skips_bluesky(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from pipeline.live import _collect_posts
    from pipeline.store import connect, record_fetched_days, replace_posts

    database = tmp_path / "live.db"
    connection = connect(database)
    kept = {
        "uri": "at://today",
        "author": "ada",
        "text": "A post from today that is already inside the retained window.",
        "clean_text": "A post from today that is already inside the retained window.",
        "likes": 3,
        "created_at": "2026-09-28T08:00:00Z",
    }
    replace_posts(connection, [kept])
    record_fetched_days(connection, ["2026-09-28"], fetched_at="2026-09-28T09:00:00+00:00", kept=1)

    def boom(**_kwargs):
        raise AssertionError("a recorded UTC day must not search Bluesky again")

    monkeypatch.setattr("pipeline.live.extract_posts", boom)
    cleaned, source, refreshed = _collect_posts(
        [kept],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 9, 28, 18, tzinfo=timezone.utc),
    )
    assert refreshed is False
    assert source == "bluesky"
    assert [post["uri"] for post in cleaned] == ["at://today"]
    connection.close()


def test_morning_loop_fetches_until_the_quota_or_the_source_runs_out(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from pipeline.live import _collect_posts
    from pipeline.store import connect

    connection = connect(tmp_path / "live.db")
    calls = {"n": 0}

    def fake_extract(**kwargs):
        calls["n"] += 1
        assert kwargs["window_hours"] == 168
        index = calls["n"]
        return [
            {
                "uri": f"at://batch-{index}",
                "author": "new",
                "text": f"People were arguing about rent increase number {index} on my block again today.",
                "likes": 2,
                "created_at": "2026-09-28T12:00:00Z",
            }
        ]

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    cleaned, _source, refreshed = _collect_posts(
        [],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the"]},
        None,
        None,
        3,
        connection,
        now=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    connection.close()
    assert refreshed is True
    assert calls["n"] == 3
    assert {post["uri"] for post in cleaned} == {"at://batch-1", "at://batch-2", "at://batch-3"}


def test_recluster_is_called_with_every_retained_post(monkeypatch, tmp_path):
    from pipeline import live as live_module

    fixture = tmp_path / "posts.json"
    fixture.write_text(json.dumps(build_tiny_posts()), encoding="utf-8")
    seen = {}
    real = live_module.cluster_texts

    def spy(texts, **kwargs):
        seen["n"] = len(texts)
        return real(texts, **kwargs)

    monkeypatch.setattr(live_module, "cluster_texts", spy)
    run_live(
        fixture=fixture,
        output=tmp_path / "data.json",
        config=_heuristic_config(tmp_path / "pipeline.yaml"),
        db_path=tmp_path / "posts.db",
    )
    assert seen["n"] == len(build_tiny_posts())


def test_section_columns_round_trip(tmp_path):
    from pipeline.store import connect, load_posts, replace_posts

    connection = connect(tmp_path / "posts.db")
    replace_posts(
        connection,
        [
            {
                "uri": "at://a",
                "author": "ada",
                "text": "A retained post.",
                "clean_text": "A retained post.",
                "likes": 4,
                "created_at": "2026-09-28T00:00:00Z",
                "section": "World",
                "section_confidence": 0.81,
                "spam_score": 0.05,
            }
        ],
    )
    loaded = load_posts(connection)
    connection.close()
    assert loaded[0]["section"] == "World"
    assert loaded[0]["section_confidence"] == 0.81
    assert loaded[0]["spam_score"] == 0.05


def test_planet_volume_follows_the_posts_still_on_it():
    topics = [
        {"name": "Small", "post_count": 4, "total_volume_percent": 14.1},
        {"name": "Large", "post_count": 84, "total_volume_percent": 6.2},
    ]
    publish_volumes(topics)
    assert topics[1]["total_volume_percent"] > topics[0]["total_volume_percent"]
    assert abs(sum(topic["total_volume_percent"] for topic in topics) - 100) < 0.15

