import json
import sqlite3

from pipeline.live import run_live
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


def test_neutral_refill_replaces_a_seeded_corpus(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from pipeline.live import _collect_posts
    from pipeline.store import connect, fetched_day_set, replace_posts

    database = tmp_path / "live.db"
    connection = connect(database)
    seeded = {
        "uri": "at://seeded",
        "author": "old",
        "text": "A seeded sports post about the nfl that should not survive the refill.",
        "clean_text": "A seeded sports post about the nfl that should not survive the refill.",
        "likes": 1,
        "created_at": "2026-09-01T00:00:00Z",
    }
    replace_posts(connection, [seeded])

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
    cleaned, source = _collect_posts(
        [seeded],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the", "and"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    assert source == "bluesky"
    assert [post["uri"] for post in cleaned] == ["at://fresh"]
    assert "2026-09-28" in fetched_day_set(connection)
    assert "2026-09-22" in fetched_day_set(connection)
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
    cleaned, source = _collect_posts(
        [kept],
        {"window_hours": 168, "refresh_hours": 24, "seed": 0, "neutral_queries": ["the"]},
        None,
        None,
        10,
        connection,
        now=datetime(2026, 9, 28, 18, tzinfo=timezone.utc),
    )
    assert source == "bluesky"
    assert [post["uri"] for post in cleaned] == ["at://today"]
    connection.close()


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

