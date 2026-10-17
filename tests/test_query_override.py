import pytest

from pipeline.live import run_live
from pipeline.run_pipeline import main


def test_query_rejected_in_demo():
    with pytest.raises(SystemExit):
        main(["--demo", "--query", "acme"])


def test_relabel_rejected_with_fixture():
    with pytest.raises(SystemExit):
        main(["--live", "--relabel", "--fixture", "posts.json"])


def test_run_live_passes_query_override(monkeypatch, tmp_path):
    """The default free-ingest path searches the override list, not the wide list."""
    seen = []

    def fake_extract(**kwargs):
        seen.append(kwargs["queries"])
        return []

    def old_path(**_kwargs):
        raise AssertionError("old per-post fetch ran")

    monkeypatch.setattr("pipeline.free_ingest.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.extract_posts", old_path)
    config = tmp_path / "pipeline.yaml"
    config.write_text("free_ingest: true\nwindow_hours: 168\nseed: 0\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="No quality posts"):
        run_live(
            output=tmp_path / "data.json",
            config=config,
            db_path=tmp_path / "posts.db",
            queries=["acme", "acme shoes"],
        )
    assert seen
    assert {query for batch in seen for query in batch} == {"acme", "acme shoes"}


def test_fixture_still_ignores_queries(tmp_path):
    fixture = tmp_path / "posts.json"
    fixture.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="No quality posts"):
        run_live(
            fixture=fixture,
            output=tmp_path / "data.json",
            db_path=tmp_path / "posts.db",
            queries=["acme"],
        )
