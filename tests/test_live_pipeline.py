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
    monkeypatch.setattr("pipeline.live.extract_grouped_posts", boom)
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
    monkeypatch.setattr("pipeline.live.extract_grouped_posts", forbidden)
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

