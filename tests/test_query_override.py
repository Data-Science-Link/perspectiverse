import pytest

from pipeline.live import run_live
from pipeline.run_pipeline import main


def test_query_requires_live():
    with pytest.raises(SystemExit):
        main(["--query", "acme"])


def test_run_live_passes_query_override(monkeypatch, tmp_path):
    captured = {}

    def fake_extract(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    with pytest.raises(RuntimeError, match="no posts"):
        run_live(
            output=tmp_path / "data.json",
            db_path=tmp_path / "posts.db",
            queries=["acme", "acme shoes"],
        )
    assert captured["queries"] == ["acme", "acme shoes"]


def test_fixture_still_ignores_queries(tmp_path):
    fixture = tmp_path / "posts.json"
    fixture.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Every post was dropped"):
        run_live(
            fixture=fixture,
            output=tmp_path / "data.json",
            db_path=tmp_path / "posts.db",
            queries=["acme"],
        )
