from datetime import datetime, timedelta, timezone

from pipeline.data_sources.extract_bluesky import extract_posts, normalize_post


def _post(uri, created, text="A sufficiently long English sentence about today."):
    return {
        "uri": uri,
        "author": {"handle": "ada.bsky.social"},
        "record": {"text": text, "createdAt": created},
        "likeCount": 4,
    }


def test_extract_keeps_window_and_samples():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pages = {
        "the": {
            "posts": [
                _post("at://old", stale),
                _post("at://new-1", fresh, "People are talking about rent in the city today."),
                _post("at://new-2", fresh, "People are talking about school schedules today."),
            ]
        },
        "people": {"posts": [_post("at://new-1", fresh, "duplicate should be ignored in the sample")]},
    }

    def fetch(query, cursor, limit):
        assert cursor is None
        assert limit == 100
        return pages[query]

    posts = extract_posts(
        sample_size=1,
        window_hours=168,
        queries=["the", "people"],
        fetch=fetch,
        now=now,
        rng=__import__("random").Random(0),
    )
    assert len(posts) == 1
    assert posts[0]["uri"] in {"at://new-1", "at://new-2"}
    assert posts[0]["author"] == "ada.bsky.social"
    assert posts[0]["likes"] == 4


def test_normalize_post_requires_text_and_time():
    assert normalize_post({"uri": "at://x"}) is None


def test_extract_follows_cursor_until_the_window_is_full():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    calls = []

    def fetch(query, cursor, limit):
        calls.append((query, cursor, limit))
        if cursor is None:
            return {
                "posts": [_post("at://page-1", fresh, "First page talking about rent in the city today.")],
                "cursor": "next",
            }
        return {
            "posts": [_post("at://page-2", fresh, "Second page talking about school schedules today.")],
        }

    posts = extract_posts(
        sample_size=2,
        window_hours=168,
        queries=["the"],
        fetch=fetch,
        now=now,
        rng=__import__("random").Random(0),
    )
    assert {post["uri"] for post in posts} == {"at://page-1", "at://page-2"}
    assert calls == [("the", None, 100), ("the", "next", 100)]


def test_authenticated_fetch_logs_in_once(monkeypatch):
    import sys
    import types

    from pipeline.data_sources import extract_bluesky as bluesky

    bluesky.reset_auth_state()
    logins = {"n": 0}

    class FakeResponse:
        posts = []
        cursor = None

    class FakeFeed:
        def search_posts(self, params):
            assert params["q"] == "nfl"
            return FakeResponse()

    class FakeBsky:
        feed = FakeFeed()

    class FakeApp:
        bsky = FakeBsky()

    class FakeClient:
        def __init__(self):
            self.app = FakeApp()

        def login(self, handle, password):
            logins["n"] += 1
            assert handle == "example.bsky.social"
            assert password == "app-password-not-real"

    monkeypatch.setenv("BLUESKY_HANDLE", "example.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password-not-real")
    monkeypatch.setitem(sys.modules, "atproto", types.SimpleNamespace(Client=FakeClient))

    first = bluesky._fetch_authenticated("nfl", None, 10)
    second = bluesky._fetch_authenticated("nfl", None, 10)
    assert first["posts"] == []
    assert second["posts"] == []
    assert logins["n"] == 1
    bluesky.reset_auth_state()


def test_login_failure_does_not_echo_the_app_password(monkeypatch):
    import sys
    import types

    import pytest

    from pipeline.data_sources import extract_bluesky as bluesky

    bluesky.reset_auth_state()
    secret = "app-password-not-real"

    class FakeClient:
        def login(self, handle, password):
            raise RuntimeError(f"Auth failed for {handle} using {password}")

    monkeypatch.setenv("BLUESKY_HANDLE", "example.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", secret)
    monkeypatch.setitem(sys.modules, "atproto", types.SimpleNamespace(Client=FakeClient))

    with pytest.raises(RuntimeError, match="Bluesky login failed") as caught:
        bluesky._fetch_authenticated("nfl", None, 10)
    assert secret not in str(caught.value)
    bluesky.reset_auth_state()
