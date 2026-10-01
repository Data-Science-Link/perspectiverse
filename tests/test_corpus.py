import random
from datetime import datetime, timedelta, timezone

from pipeline.corpus import cap_sample, posts_on_utc_date, quality_score, retain_window, scale_quotas, select_quality

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


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


def test_cap_sample_does_not_prefer_likes():
    incoming = [_post(f"at://{index}", hours_ago=index, likes=index) for index in range(20)]
    kept = cap_sample(incoming, 10, random.Random(0))
    assert len(kept) == 10
    assert {post["uri"] for post in kept} != {f"at://{index}" for index in range(10, 20)}


def test_expiry_drops_the_eighth_day_when_today_arrives():
    existing = [_post("at://old", hours_ago=200), _post("at://keep", hours_ago=10)]
    incoming = [_post("at://new", hours_ago=1)]
    kept = retain_window(existing, incoming, now=NOW, window_hours=168, target=10, rng=random.Random(0))
    assert {post["uri"] for post in kept} == {"at://keep", "at://new"}


def test_failed_fetch_does_not_shrink_the_window():
    existing = [_post("at://old", hours_ago=200), _post("at://keep", hours_ago=10)]
    assert retain_window(existing, [], now=NOW, window_hours=168, target=10, rng=random.Random(0)) == existing


def test_full_window_does_not_swap_in_window_posts_for_likes():
    existing = [_post(f"at://old-{index}", hours_ago=index + 1, likes=1) for index in range(7)]
    incoming = [_post("at://new", hours_ago=1, likes=50)]
    kept = retain_window(existing, incoming, now=NOW, window_hours=168, target=7, rng=random.Random(0))
    assert {post["uri"] for post in kept} == {post["uri"] for post in existing}


def test_duplicate_fetch_does_not_drop_posts():
    existing = [_post(f"at://old-{index}", hours_ago=20 - index) for index in range(7)]
    kept = retain_window(existing, [dict(existing[0])], now=NOW, window_hours=168, target=7, rng=random.Random(0))
    assert {post["uri"] for post in kept} == {post["uri"] for post in existing}


def test_posts_on_utc_date_uses_the_calendar_day():
    posts = [_post("at://today", hours_ago=1)]
    assert posts_on_utc_date(posts, "2026-09-27")
    assert not posts_on_utc_date(posts, "2026-09-28")


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
