from datetime import datetime, timedelta, timezone

from pipeline.corpus import quality_score, rotate_corpus, scale_quotas, select_quality


def _post(uri: str, hours_ago: int, likes: int = 4, text: str = "A long enough public argument about the week."):
    created = datetime(2026, 9, 28, tzinfo=timezone.utc) - timedelta(hours=hours_ago)
    return {
        "uri": uri,
        "author": "ada.bsky.social",
        "text": text,
        "clean_text": text,
        "likes": likes,
        "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def test_first_fill_keeps_the_best_target():
    incoming = [_post(f"at://{index}", hours_ago=index, likes=index) for index in range(20)]
    kept = rotate_corpus([], incoming, target=10)
    assert len(kept) == 10
    assert max(post["likes"] for post in kept) == 19


def test_rotate_drops_oldest_seventh_and_adds_fresh():
    existing = [_post(f"at://old-{index}", hours_ago=200 - index, likes=1) for index in range(7)]
    incoming = [_post("at://new", hours_ago=1, likes=20)]
    rotated = rotate_corpus(existing, incoming, target=7, drop_fraction=1 / 7)
    assert "at://old-0" not in {post["uri"] for post in rotated}
    assert "at://new" in {post["uri"] for post in rotated}
    assert len(rotated) == 7


def test_failed_fetch_does_not_shrink_the_window():
    existing = [_post(f"at://keep-{index}", hours_ago=index) for index in range(10)]
    assert rotate_corpus(existing, [], target=10) == existing


def test_quality_prefers_liked_argumentative_posts():
    weak = _post("at://weak", 1, likes=0, text="hello there everybody in this place now")
    strong = _post("at://strong", 1, likes=40, text="The league changed the playoff format and the players are furious about it.")
    assert quality_score(strong) > quality_score(weak)
    assert select_quality([weak, strong], 1)[0]["uri"] == "at://strong"


def test_scale_quotas_keeps_a_ten_post_floor():
    quotas = scale_quotas(80)
    assert quotas["sports"] >= 10
    assert quotas["geopolitics"] >= 10
    assert quotas["ai"] >= 10
    assert sum(quotas.values()) == 80
