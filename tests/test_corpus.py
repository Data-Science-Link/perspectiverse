import random
from datetime import datetime, timedelta, timezone

from pipeline.corpus import (
    CLAIM_TARGET,
    cap_sample,
    counted_posts,
    keep_claims,
    posts_on_utc_date,
    quality_score,
    refresh_floor,
    retain_window,
    retire_oldest,
    scale_quotas,
    select_quality,
)

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


def test_keep_claims_ignores_non_claims_and_caps_the_rest():
    posts = []
    for index in range(5):
        post = _post(f"at://claim-{index}", hours_ago=1)
        post["is_claim"] = True
        posts.append(post)
    aside = _post("at://aside", hours_ago=1)
    aside["is_claim"] = False
    posts.append(aside)
    kept = keep_claims(posts, 3, random.Random(0))
    assert sum(1 for post in kept if post.get("is_claim") is True) == 3
    assert any(post["uri"] == "at://aside" for post in kept)
    assert CLAIM_TARGET == 10000


def test_uncapped_retain_keeps_posts_past_the_old_ceiling():
    existing = [_post("at://keep", hours_ago=10)]
    incoming = [_post(f"at://new-{index}", hours_ago=1) for index in range(4)]
    kept = retain_window(
        existing,
        incoming,
        now=NOW,
        window_hours=168,
        target=2,
        rng=random.Random(0),
        cap=False,
    )
    assert len(kept) == 5


def test_refresh_floor_is_one_seventh_rounded_up():
    assert refresh_floor(10000) == 1429
    assert refresh_floor(7) == 1
    assert refresh_floor(8) == 2
    assert refresh_floor(0) == 0


def test_retire_drops_the_eighth_day_and_then_the_oldest_surplus():
    posts = []
    for index in range(12):
        post = _post(f"at://p-{index}", hours_ago=index + 1)
        post["is_claim"] = True
        posts.append(post)
    stale = _post("at://stale", hours_ago=200)
    stale["is_claim"] = True
    posts.append(stale)
    aside = _post("at://aside", hours_ago=2)
    aside["is_claim"] = False
    posts.append(aside)
    kept = retire_oldest(posts, now=NOW, window_hours=168, target=10)
    uris = {post["uri"] for post in kept}
    assert "at://stale" not in uris
    assert "at://aside" in uris
    assert "at://p-11" not in uris
    assert "at://p-10" not in uris
    assert "at://p-0" in uris
    assert len(counted_posts(kept)) == 10


def test_scale_quotas_keeps_a_ten_post_floor():
    quotas = scale_quotas(80)
    assert quotas["sports"] >= 10
    assert quotas["geopolitics"] >= 10
    assert quotas["ai"] >= 10
    assert sum(quotas.values()) == 80
