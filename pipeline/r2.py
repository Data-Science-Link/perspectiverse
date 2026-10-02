"""Cloudflare R2 home for the retained SQLite corpus.

The daily job downloads ``live_corpus.db`` and passes that path to ``--db``.
It uploads the same file only after the pipeline exits 0 and
``PRAGMA integrity_check`` still returns ``ok``. A single PUT replaces the
object only when R2 accepts the whole body, so a dropped connection leaves
the previous object in place.

``data.json`` is not stored here. Pages keeps publishing that file from git.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CORPUS_KEY = "live_corpus.db"
_OBJECT_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.db")
DEFAULT_BUCKET = "perspectiverse-corpus"
_REGION = "auto"
_SERVICE = "s3"
_REQUIRED_TABLES = ("posts", "fetched_days", "topic_membership", "perspectives")
_CHUNK = 1024 * 1024


class CorpusAbsent(RuntimeError):
    """The bucket does not have ``live_corpus.db`` yet."""


@dataclass(frozen=True)
class R2Config:
    """S3-compatible credentials for the private corpus bucket."""

    access_key_id: str
    endpoint: str
    secret_access_key: str = field(repr=False)
    bucket: str = DEFAULT_BUCKET
    region: str = _REGION
    object_key: str = CORPUS_KEY
    timeout: float = 600.0


def load_r2_config(environ: Mapping[str, str] | None = None) -> R2Config | None:
    """Read R2 settings. ``None`` means the daily job should keep using git.

    A partial set is an error. Guessing would let a stale seed overwrite the
    last good object, or skip an upload the operator thought was configured.
    """
    env = os.environ if environ is None else environ
    access_key = _setting(env, "R2_ACCESS_KEY_ID")
    secret = _setting(env, "R2_SECRET_ACCESS_KEY")
    endpoint = _setting(env, "R2_ENDPOINT").rstrip("/")
    bucket = _setting(env, "R2_BUCKET") or DEFAULT_BUCKET
    object_key = _setting(env, "R2_OBJECT_KEY") or CORPUS_KEY
    if not access_key and not secret and not endpoint:
        return None
    missing = [
        name
        for name, value in (
            ("R2_ACCESS_KEY_ID", access_key),
            ("R2_SECRET_ACCESS_KEY", secret),
            ("R2_ENDPOINT", endpoint),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "R2 is partially configured. Set " + ", ".join(missing) + " along with the other R2 secrets."
        )
    config = R2Config(
        access_key_id=access_key,
        secret_access_key=secret,
        endpoint=endpoint,
        bucket=bucket,
        object_key=object_key,
    )
    _validate_config(config)
    return config


def assert_corpus_publishable(path: Path) -> None:
    """Reject a missing, truncated, or half-written database before any PUT."""
    database = Path(path)
    if not database.is_file():
        raise RuntimeError(f"Refusing a missing corpus: {database}")
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = database.with_name(database.name + suffix)
        if sidecar.exists():
            raise RuntimeError("Refusing a corpus while SQLite still has a sidecar file")
    with database.open("rb") as handle:
        header = handle.read(16)
    if header != b"SQLite format 3\x00":
        raise RuntimeError("Refusing a file that is not a SQLite database")
    connection = sqlite3.connect(_readonly_uri(database), uri=True)
    try:
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        except sqlite3.DatabaseError as exc:
            raise RuntimeError("Refusing a truncated corpus") from exc
        if rows != [("ok",)]:
            raise RuntimeError("Refusing a corpus that failed integrity_check")
        found = {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        missing = [name for name in _REQUIRED_TABLES if name not in found]
        if missing:
            raise RuntimeError("Refusing a corpus missing tables: " + ", ".join(missing))
    finally:
        connection.close()


def restore_corpus(
    path: Path,
    *,
    config: R2Config | None = None,
    opener=None,
    environ: dict[str, str] | None = None,
) -> str:
    """Download the corpus over ``path``.

    Returns ``downloaded``, ``absent``, or ``unconfigured``. A 404 leaves
    ``path`` untouched so the git seed can fill the bucket. Any other failure
    leaves ``path`` untouched and raises, so that seed is not uploaded later.
    """
    resolved = _resolve(config, environ)
    if resolved is None:
        return "unconfigured"
    try:
        _download(resolved, Path(path), opener)
    except CorpusAbsent:
        return "absent"
    return "downloaded"


def upload_corpus(
    path: Path,
    *,
    config: R2Config | None = None,
    opener=None,
    environ: dict[str, str] | None = None,
) -> str:
    """PUT a publishable corpus. Returns ``uploaded`` or ``unconfigured``.

    The caller (the workflow) must already have skipped this after a failed
    pipeline step. This function still refuses a truncated file.
    """
    resolved = _resolve(config, environ)
    if resolved is None:
        return "unconfigured"
    database = Path(path)
    assert_corpus_publishable(database)
    _upload(resolved, database, opener)
    return "uploaded"


def _resolve(config: R2Config | None, environ: dict[str, str] | None) -> R2Config | None:
    if config is not None:
        _validate_config(config)
        return config
    return load_r2_config(environ)


def _setting(env, name: str) -> str:
    return str(env.get(name) or "").strip()


def _valid_object_key(key: str) -> bool:
    return bool(_OBJECT_KEY.fullmatch(key or ""))


def _validate_config(config: R2Config) -> None:
    if config.region != _REGION or not _valid_object_key(config.object_key):
        raise RuntimeError("The corpus object must be a .db name in region auto")
    _validate_endpoint(config.endpoint)
    _validate_bucket(config.bucket)
    if not config.access_key_id or not config.secret_access_key:
        raise RuntimeError("R2 credentials are empty")


def _validate_endpoint(endpoint: str) -> None:
    parsed = urllib.parse.urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or not host.endswith(".r2.cloudflarestorage.com")
    ):
        raise RuntimeError("R2_ENDPOINT must be the https account host (*.r2.cloudflarestorage.com)")


def _validate_bucket(bucket: str) -> None:
    if len(bucket) < 3 or len(bucket) > 63:
        raise RuntimeError("R2_BUCKET must be a private bucket name such as perspectiverse-corpus")
    alnum = set("abcdefghijklmnopqrstuvwxyz0123456789")
    allowed = alnum | {"-"}
    if bucket[0] not in alnum or bucket[-1] not in alnum or any(char not in allowed for char in bucket):
        raise RuntimeError("R2_BUCKET must be a private bucket name such as perspectiverse-corpus")
    if "--" in bucket:
        raise RuntimeError("R2_BUCKET must be a private bucket name such as perspectiverse-corpus")


def _readonly_uri(path: Path) -> str:
    quoted = urllib.parse.quote(path.resolve().as_posix(), safe="/")
    return f"file:{quoted}?mode=ro"


def _download(config: R2Config, path: Path, opener) -> None:
    request = _signed_request(config, "GET", b"")
    response = _exchange(request, config.timeout, opener)
    partial = path.with_name(path.name + ".partial")
    try:
        status = _status(response)
        if status == 404:
            raise CorpusAbsent(config.object_key)
        if status != 200:
            raise RuntimeError(f"R2 download failed with HTTP {status}")
        expected = _content_length(response)
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
        if expected is not None and written != expected:
            raise RuntimeError(f"R2 download ended early ({written} bytes of {expected})")
        assert_corpus_publishable(partial)
        os.replace(partial, path)
    finally:
        _close(response)
        partial.unlink(missing_ok=True)


def _upload(config: R2Config, path: Path, opener) -> None:
    payload = path.read_bytes()
    request = _signed_request(config, "PUT", payload)
    response = _exchange(request, config.timeout, opener)
    try:
        status = _status(response)
        response.read()
        if status != 200:
            raise RuntimeError(f"R2 upload failed with HTTP {status}")
    finally:
        _close(response)


def _exchange(request, timeout: float, opener):
    open_ = opener or _urlopen
    return open_(request, timeout)


def _urlopen(request, timeout: float):
    try:
        return _OPENER.open(request, timeout=timeout)  # nosec B310
    except urllib.error.HTTPError as exc:
        return exc


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would send the signed request at a different host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f"Refusing to follow an R2 HTTP {code} redirect")


_OPENER = urllib.request.build_opener(_RefuseRedirect)


def _status(response) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = getattr(response, "code", None)
    if status is None:
        raise RuntimeError("R2 response did not include a status code")
    return int(status)


def _content_length(response) -> int | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Content-Length")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("R2 sent a Content-Length that is not an integer") from exc


def _close(response) -> None:
    close = getattr(response, "close", None)
    if close:
        close()


def _signed_request(config: R2Config, method: str, payload: bytes) -> urllib.request.Request:
    payload_hash = hashlib.sha256(payload).hexdigest()
    amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = urllib.parse.urlparse(config.endpoint).hostname or ""
    headers = {
        "Host": host,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
    }
    if method == "PUT":
        headers["Content-Type"] = "application/octet-stream"
    signed = _authorization_header(
        method=method,
        canonical_uri=_canonical_uri(config),
        signed_headers=headers,
        payload_hash=payload_hash,
        access_key_id=config.access_key_id,
        secret_access_key=config.secret_access_key,
        region=config.region,
        amz_date=amz_date,
    )
    headers["Authorization"] = signed
    url = f"{config.endpoint}{_canonical_uri(config)}"
    data = payload if method == "PUT" else None
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def _canonical_uri(config: R2Config) -> str:
    return "/" + _quote_segment(config.bucket) + "/" + _quote_segment(config.object_key)


def _quote_segment(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def _authorization_header(
    *,
    method: str,
    canonical_uri: str,
    signed_headers: dict[str, str],
    payload_hash: str,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    amz_date: str,
    service: str = _SERVICE,
) -> str:
    """AWS Signature Version 4 for one S3-compatible request."""
    date_stamp = amz_date[:8]
    canonical_headers, header_names = _canonicalize_headers(signed_headers)
    canonical_request = (
        f"{method}\n{canonical_uri}\n\n{canonical_headers}\n{header_names}\n{payload_hash}"
    )
    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        (
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )
    signature = hmac.new(
        _signing_key(secret_access_key, date_stamp, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key_id}/{scope},"
        f"SignedHeaders={header_names},"
        f"Signature={signature}"
    )


def _canonicalize_headers(headers: dict[str, str]) -> tuple[str, str]:
    normalized = {
        key.lower().strip(): " ".join(value.strip().split())
        for key, value in headers.items()
    }
    names = sorted(normalized)
    block = "".join(f"{name}:{normalized[name]}\n" for name in names)
    return block, ";".join(names)


def _signing_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    key = ("AWS4" + secret).encode("utf-8")
    for part in (date_stamp, region, service, "aws4_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    return key


def main(argv: list[str] | None = None) -> None:
    from pipeline.settings import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Download or upload the retained corpus in Cloudflare R2")
    commands = parser.add_subparsers(dest="command", required=True)
    restore = commands.add_parser("restore", help="Download live_corpus.db when R2 is configured")
    restore.add_argument("path", type=Path)
    upload = commands.add_parser("upload", help="Upload a checked SQLite corpus after a successful run")
    upload.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "restore":
            print(restore_corpus(args.path))
        else:
            print(upload_corpus(args.path))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
