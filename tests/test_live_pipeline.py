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


def test_run_live_function_matches_cli(tmp_path):
    fixture = tmp_path / "posts.json"
    fixture.write_text(json.dumps(build_tiny_posts()), encoding="utf-8")
    config = tmp_path / "pipeline.yaml"
    config.write_text("min_cluster_size: 8\ncluster_backend: lexical\nlabel_backend: heuristic\nseed: 0\n", encoding="utf-8")
    path = run_live(fixture=fixture, output=tmp_path / "out.json", config=config, db_path=tmp_path / "p.db")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["topics"][0]["perspectives"]) == 6
    assert payload["topics"][0]["perspectives"][0]["representative_posts"][0]["likes"] >= 0
