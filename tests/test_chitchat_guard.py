"""Chit-chat guard: ingest filter and planet guard (#208)."""

from pipeline.chitchat_guard import (
    chitchat_reason,
    filter_chitchat_posts,
    ingest_block_reason,
    planet_chitchat_reason,
    reset_chitchat_log,
)
from pipeline.free_ingest import keep_edition_quality


def test_thanks_birthday_stream_and_agreement_are_chitchat():
    assert chitchat_reason({"text": "Thank you so much!"}) == "thanks"
    assert chitchat_reason({"text": "Happy birthday!! Hope you have a great day"}) == "wish"
    assert chitchat_reason({"text": "We are live now on twitch.tv/example"}) == "stream_announce"
    assert chitchat_reason({"text": "Of course"}) == "agreement"
    assert chitchat_reason({"text": "Count me in"}) == "agreement"
    assert chitchat_reason({"text": "Have a great weekend!"}) == "weekend"


def test_veterans_thanks_and_streaming_policy_are_not_chitchat():
    veterans = {
        "text": (
            "Thank you to every veteran who served. Congress should fund the VA "
            "and fix the backlog before the next election."
        )
    }
    policy = {
        "text": (
            "Twitch's new moderation policy will change how streamers handle politics "
            "on the platform and what counts as acceptable speech during live broadcasts."
        )
    }
    assert chitchat_reason(veterans) is None
    assert chitchat_reason(policy) is None
    assert ingest_block_reason(veterans) is None
    assert ingest_block_reason(policy) is None


def test_ingest_filter_drops_chitchat_before_spam_count_only_quality():
    reset_chitchat_log()
    posts = [
        {"uri": "at://ok", "text": "City council should vote on rent control this month."},
        {"uri": "at://thanks", "text": "Thanks!!"},
        {
            "uri": "at://spam",
            "text": "Now playing on KB Radio: Fantasy! Tune in now: https://radio.example/listen",
        },
    ]
    kept, blocked_spam, blocked_other = keep_edition_quality(posts)
    assert len(kept) == 1
    assert kept[0]["uri"] == "at://ok"
    assert blocked_spam == 1
    assert blocked_other == 1


def test_planet_guard_drops_high_share_chitchat_clusters():
    members = [{"text": "Thank you!"} for _ in range(8)] + [{"text": "Beautiful work!"} for _ in range(2)]
    reason = planet_chitchat_reason(members, ["appreciation"], name="Art Appreciation")
    assert reason is not None
    assert "chitchat" in reason.lower() or "%" in reason


def test_planet_guard_keeps_discourse_news_planet():
    members = [
        {
            "text": (
                "The Senate bill would require streaming platforms to report child safety "
                "violations within 24 hours or face federal fines."
            )
        }
        for _ in range(6)
    ]
    assert planet_chitchat_reason(members, ["streaming", "policy"], name="Streaming Policy") is None


def test_filter_chitchat_posts_returns_kept_and_dropped():
    posts = [
        {"text": "School boards need a clear policy on library books."},
        {"text": "Yes!"},
    ]
    kept, dropped = filter_chitchat_posts(posts)
    assert len(kept) == 1
    assert dropped == 1
