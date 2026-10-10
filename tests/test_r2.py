"""R2 corpus sync: signature, failed downloads, and no upload of a bad file."""

import hashlib
import json
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.r2 import (
    _authorization_header,
    assert_corpus_publishable,
    load_r2_config,
    main,
    restore_corpus,
    upload_corpus,
)
from pipeline.schema import validate_payload
from tests.corpus import build_tiny_posts

_EMPTY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_ENDPOINT = "https://acct.r2.cloudflarestorage.com"


class _Resp:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self.headers = headers or {}
        self._body = body
        self._offset = 0

    def read(self, amount=-1):
        if amount is None or amount < 0:
            chunk = self._body[self._offset :]
            self._offset = len(self._body)
            return chunk
        chunk = self._body[self._offset : self._offset + amount]
        self._offset += len(chunk)
        return chunk

    def close(self):
        return None


def _config():
    from pipeline.r2 import R2Config

    return R2Config(
        access_key_id="AKIDEXAMPLE",
        endpoint=_ENDPOINT,
        secret_access_key="secret",
        bucket="perspectiverse-corpus",
    )


def _headers(request):
    return {key.lower(): value for key, value in request.header_items()}


def _write_corpus(path: Path, *, day: str = "2026-09-28") -> None:
    from pipeline.cleaning import clean_posts
    from pipeline.store import connect, record_fetched_days, replace_posts

    posts = clean_posts(build_tiny_posts())
    for post in posts:
        post["created_at"] = f"{day}T12:00:00Z"
    connection = connect(path)
    replace_posts(connection, posts)
    record_fetched_days(connection, [day], fetched_at=f"{day}T13:00:00+00:00", kept=len(posts))
    connection.close()


class _MemoryR2:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append(request.get_method())
        headers = _headers(request)
        assert headers["authorization"].startswith("AWS4-HMAC-SHA256 ")
        assert "/auto/s3/aws4_request" in headers["authorization"]
        assert headers["host"] == "acct.r2.cloudflarestorage.com"
        path = urllib.parse.urlparse(request.full_url).path
        assert path == "/perspectiverse-corpus/live_corpus.db"
        if request.get_method() == "PUT":
            body = request.data
            assert isinstance(body, bytes)
            assert headers["x-amz-content-sha256"] == hashlib.sha256(body).hexdigest()
            assert "secret" not in headers["authorization"]
            self.objects[path] = body
            return _Resp(200, b"")
        if request.get_method() == "HEAD":
            if path not in self.objects:
                return _Resp(404, b"")
            body = self.objects[path]
            return _Resp(200, b"", headers={"Content-Length": str(len(body))})
        if request.get_method() == "GET":
            if path not in self.objects:
                return _Resp(404, b"missing")
            body = self.objects[path]
            return _Resp(200, body, headers={"Content-Length": str(len(body))})
        raise AssertionError(request.get_method())


def test_sigv4_matches_the_aws_get_object_example():
    """Lock the signer to the published AWS SigV4 GET Object example."""
    header = _authorization_header(
        method="GET",
        canonical_uri="/test.txt",
        signed_headers={
            "Host": "examplebucket.s3.amazonaws.com",
            "Range": "bytes=0-9",
            "x-amz-content-sha256": _EMPTY_HASH,
            "x-amz-date": "20130524T000000Z",
        },
        payload_hash=_EMPTY_HASH,
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        amz_date="20130524T000000Z",
    )
    assert header == (
        "AWS4-HMAC-SHA256 "
        "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


def test_r2_config_requires_the_account_host_and_defaults_the_bucket():
    assert load_r2_config({}) is None
    config = load_r2_config(
        {
            "R2_ACCESS_KEY_ID": "AKID",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_ENDPOINT": _ENDPOINT + "/",
        }
    )
    assert config is not None
    assert config.bucket == "perspectiverse-corpus"
    assert config.object_key == "live_corpus.db"
    preview = load_r2_config(
        {
            "R2_ACCESS_KEY_ID": "AKID",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_ENDPOINT": _ENDPOINT,
            "R2_OBJECT_KEY": "live_corpus_preview.db",
        }
    )
    assert preview is not None
    assert preview.object_key == "live_corpus_preview.db"
    with pytest.raises(RuntimeError, match="\\.db"):
        load_r2_config(
            {
                "R2_ACCESS_KEY_ID": "AKID",
                "R2_SECRET_ACCESS_KEY": "secret",
                "R2_ENDPOINT": _ENDPOINT,
                "R2_OBJECT_KEY": "../live_corpus.db",
            }
        )
    assert config.endpoint == _ENDPOINT
    assert "secret" not in repr(config)
    with pytest.raises(RuntimeError, match="partially configured"):
        load_r2_config({"R2_ACCESS_KEY_ID": "AKID"})
    with pytest.raises(RuntimeError, match="r2.cloudflarestorage.com"):
        load_r2_config(
            {
                "R2_ACCESS_KEY_ID": "AKID",
                "R2_SECRET_ACCESS_KEY": "secret",
                "R2_ENDPOINT": "https://evil.example/bucket",
            }
        )
    with pytest.raises(RuntimeError, match="perspectiverse-corpus"):
        load_r2_config(
            {
                "R2_ACCESS_KEY_ID": "AKID",
                "R2_SECRET_ACCESS_KEY": "secret",
                "R2_ENDPOINT": _ENDPOINT,
                "R2_BUCKET": "../etc",
            }
        )


def test_upload_refuses_a_truncated_database_without_calling_r2(tmp_path):
    path = tmp_path / "live_corpus.db"
    _write_corpus(path)
    original = path.read_bytes()
    path.write_bytes(original[: len(original) // 2])

    def opener(request, timeout):
        raise AssertionError("a truncated corpus must not be uploaded")

    with pytest.raises(RuntimeError, match="truncated|integrity_check"):
        upload_corpus(path, config=_config(), opener=opener)


def test_upload_refuses_a_database_missing_the_ledger(tmp_path):
    path = tmp_path / "live_corpus.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE posts (uri TEXT)")
    connection.commit()
    connection.close()

    def opener(request, timeout):
        raise AssertionError("a partial schema must not be uploaded")

    with pytest.raises(RuntimeError, match="missing tables"):
        upload_corpus(path, config=_config(), opener=opener)


def test_unconfigured_r2_does_not_call_the_network(tmp_path):
    path = tmp_path / "live_corpus.db"
    _write_corpus(path)

    def opener(request, timeout):
        raise AssertionError("unset R2 secrets must leave the corpus on git")

    assert restore_corpus(path, opener=opener, environ={}) == "unconfigured"
    assert upload_corpus(path, opener=opener, environ={}) == "unconfigured"


def test_missing_object_and_failed_download_keep_the_local_seed(tmp_path):
    path = tmp_path / "live_corpus.db"
    _write_corpus(path)
    before = path.read_bytes()

    def missing(request, timeout):
        return _Resp(404, b"")

    assert restore_corpus(path, config=_config(), opener=missing) == "absent"
    assert path.read_bytes() == before

    def failed(request, timeout):
        return _Resp(500, b"nope")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        restore_corpus(path, config=_config(), opener=failed)
    assert path.read_bytes() == before

    def short(request, timeout):
        return _Resp(200, b"SQLite format 3\x00short", headers={"Content-Length": "9999"})

    with pytest.raises(RuntimeError, match="ended early"):
        restore_corpus(path, config=_config(), opener=short)
    assert path.read_bytes() == before
    assert not path.with_name(path.name + ".partial").exists()


def test_round_trip_clusters_without_searching_a_fetched_day(monkeypatch, tmp_path):
    day = datetime.now(timezone.utc).date().isoformat()
    source = tmp_path / "seed.db"
    _write_corpus(source, day=day)
    remote = _MemoryR2()
    assert upload_corpus(source, config=_config(), opener=remote) == "uploaded"

    restored = tmp_path / "live_corpus.db"
    assert restore_corpus(restored, config=_config(), opener=remote) == "downloaded"
    assert restored.read_bytes() == source.read_bytes()
    connection = sqlite3.connect(restored)
    assert day in {row[0] for row in connection.execute("SELECT utc_date FROM fetched_days")}
    kept = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    connection.close()

    def boom(**_kwargs):
        raise AssertionError("a restored fetched day must not search Bluesky")

    monkeypatch.setattr("pipeline.live.extract_posts", boom)
    monkeypatch.setattr(
        "pipeline.live.apply_jev",
        lambda posts, **_kwargs: [{**post, "is_claim": True, "section": post.get("section") or "Other"} for post in posts],
    )
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
    from pipeline.live import run_live

    output = run_live(output=tmp_path / "data.json", config=config, db_path=restored)
    payload = json.loads(output.read_text(encoding="utf-8"))
    validate_payload(payload)
    assert payload["mode"] == "live"
    assert payload["source"] == "bluesky"
    assert payload["total_posts"] == kept
    assert len(payload["topics"]) == 10
    assert remote.calls == ["PUT", "HEAD", "GET"]


def test_cli_upload_rejects_garbage_without_leaking_the_secret(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKID")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "super-secret-value")
    monkeypatch.setenv("R2_ENDPOINT", _ENDPOINT)
    monkeypatch.setenv("R2_BUCKET", "perspectiverse-corpus")
    path = tmp_path / "live_corpus.db"
    path.write_bytes(b"not a database")
    with pytest.raises(SystemExit) as exc:
        main(["upload", str(path)])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "super-secret-value" not in captured.err
    assert "super-secret-value" not in captured.out
    assert "SQLite" in captured.err


def test_publishable_corpus_passes_the_check(tmp_path):
    path = tmp_path / "live_corpus.db"
    _write_corpus(path)
    assert_corpus_publishable(path)


def test_upload_counts_put_as_class_a_and_head_plus_get_as_class_b(tmp_path, monkeypatch):
    usage_path = tmp_path / "r2_usage.json"
    monkeypatch.setattr("pipeline.costs.R2_USAGE_PATH", usage_path)
    source = tmp_path / "seed.db"
    _write_corpus(source)
    remote = _MemoryR2()
    assert upload_corpus(source, config=_config(), opener=remote) == "uploaded"
    restored = tmp_path / "restored.db"
    assert restore_corpus(restored, config=_config(), opener=remote) == "downloaded"
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    assert remote.calls == ["PUT", "HEAD", "GET"]
    assert usage["class_a_ops"] == 1
    assert usage["class_b_ops"] == 2
    assert usage["storage_known"] is True
    assert usage["storage_bytes"] == source.stat().st_size


def test_head_failure_still_uploads_and_keeps_the_file_size(tmp_path, monkeypatch):
    usage_path = tmp_path / "r2_usage.json"
    monkeypatch.setattr("pipeline.costs.R2_USAGE_PATH", usage_path)
    source = tmp_path / "seed.db"
    _write_corpus(source)

    class _HeadDown(_MemoryR2):
        def __call__(self, request, timeout):
            if request.get_method() == "HEAD":
                self.calls.append("HEAD")
                raise RuntimeError("head down")
            return super().__call__(request, timeout)

    remote = _HeadDown()
    assert upload_corpus(source, config=_config(), opener=remote) == "uploaded"
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    assert usage["class_a_ops"] == 1
    assert usage["class_b_ops"] == 0
    assert usage["storage_known"] is True
    assert usage["storage_bytes"] == source.stat().st_size


def test_a_response_is_counted_and_a_dropped_request_is_not(tmp_path, monkeypatch):
    usage_path = tmp_path / "r2_usage.json"
    monkeypatch.setattr("pipeline.costs.R2_USAGE_PATH", usage_path)
    path = tmp_path / "live_corpus.db"
    _write_corpus(path)

    def missing(request, timeout):
        return _Resp(404, b"missing")

    assert restore_corpus(path, config=_config(), opener=missing) == "absent"
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    assert usage["class_b_ops"] == 1
    assert usage["class_a_ops"] == 0
    assert usage["storage_known"] is False

    def unauthorized(request, timeout):
        return _Resp(401, b"no")

    with pytest.raises(RuntimeError, match="HTTP 401"):
        restore_corpus(path, config=_config(), opener=unauthorized)
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    assert usage["class_b_ops"] == 1

    def boom(request, timeout):
        raise RuntimeError("no response")

    with pytest.raises(RuntimeError, match="no response"):
        restore_corpus(path, config=_config(), opener=boom)
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    assert usage["class_b_ops"] == 1


def test_daily_workflow_uploads_only_after_a_successful_run():
    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    pages = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "python -m pipeline.r2 restore pipeline/data/live_corpus.db" in workflow
    assert "python -m pipeline.r2 upload pipeline/data/live_corpus.db" in workflow
    upload_step = workflow.index("name: Upload corpus to R2")
    upload_command = workflow.index("python -m pipeline.r2 upload")
    assert "steps.live.outcome == 'success'" in workflow[upload_step:upload_command]
    publish_at = workflow.index("Publish data-snapshot branch")
    publish_window = workflow[publish_at : publish_at + 500]
    assert "steps.r2upload.outcome == 'success'" in publish_window
    assert "git rm -f --ignore-unmatch pipeline/data/live_corpus.db" in workflow
    assert "r2_usage.json" in workflow
    assert "--r2-usage" in workflow
    assert "costs/daily_spend_14d.svg" in workflow
    assert "if [ -f /tmp/perspectiverse-snapshot/costs/ledger.csv ]" in workflow
    assert "if [ -f /tmp/perspectiverse-snapshot/costs/README.md ]" in workflow
    assert "if [ -f /tmp/perspectiverse-snapshot/costs/daily_spend_14d.svg ]" in workflow
    assert "public/data.json" in pages
    assert "live_corpus.db" not in pages
    assert "cp pipeline/publish_guard.py /tmp/perspectiverse-snapshot/publish_guard.py" in workflow
    assert 'python "$GUARD"' in workflow
    assert "Publish guard could not run" in workflow
    copy_at = workflow.index("cp pipeline/publish_guard.py /tmp/perspectiverse-snapshot/publish_guard.py")
    checkout_at = workflow.index("git checkout --force -B data-snapshot")
    guard_at = workflow.index("# BEGIN publish-guard")
    assert copy_at < checkout_at < guard_at
    assert '"$guard_status" -eq 10' in workflow
    assert "HOLD" in workflow
    assert "label_run.json" in workflow
    assert "not replacing public/data.json" in workflow
