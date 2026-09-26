from pipeline.cleaning import clean_posts, clean_text, is_spam


def test_clean_text_strips_urls_and_handles():
    cleaned = clean_text("See https://example.com/a and @alice.bsky for the thread")
    assert "http" not in cleaned
    assert "@" not in cleaned
    assert "thread" in cleaned


def test_spam_and_short_posts_are_dropped():
    posts = [
        {"uri": "a", "author": "ann", "text": "A real sentence about housing costs in the city today.", "likes": 3, "created_at": "t"},
        {"uri": "b", "author": "bot", "text": "hi", "likes": 0, "created_at": "t"},
        {"uri": "c", "author": "bot", "text": "aaaaaaaaaaaa look at this amazing offer now", "likes": 0, "created_at": "t"},
        {"uri": "d", "author": "bot", "text": "buy followers buy followers and grow overnight please", "likes": 0, "created_at": "t"},
        {"uri": "a", "author": "ann", "text": "A real sentence about housing costs in the city today.", "likes": 9, "created_at": "t"},
    ]
    kept = clean_posts(posts)
    assert [post["uri"] for post in kept] == ["a"]
    assert kept[0]["likes"] == 3
    assert is_spam("hi")
