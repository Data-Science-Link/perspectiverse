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
