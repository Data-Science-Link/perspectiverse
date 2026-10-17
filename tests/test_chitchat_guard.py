"""Chit-chat guard: ingest filter and post-label planet guard (#208)."""

import json
from pathlib import Path

from pipeline.chitchat_guard import (
    ingest_block_reason,
    planet_chitchat_reason,
    pleasantry_reason,
    substantive_tokens,
)
from pipeline.free_ingest import keep_edition_quality

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "chitchat_preview_posts.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_preview_representatives_that_should_be_pleasantries():
    fixture = _load_fixture()
    must_drop = [
        "thank you!! 💕💕💕",
        "happy late birthday !! 🎂🎉💖✨",
        "for sure",
        "Of course lol",
        "Wishing everyone a fun weekend!",
        "Stream is starting soon! twitch.tv/DoPeY5007",
        "LIVE NOW! Come hop in and hang out!! #Twitch #Stream #Live",
    ]
    for text in must_drop:
        assert pleasantry_reason({"text": text}) is not None, text


def test_preview_discourse_negatives_from_artifact_and_review():
    kept = [
        "The anniversary of the invasion is not a happy anniversary for Ukraine.",
        "Happy anniversary of the Voting Rights Act, which Congress still has to defend.",
        "Residents can watch live as the council votes on the housing bill tonight.",
        "The jobs report was amazing and wages finally rose.",
        "This court ruling is wonderful for renters.",
        "Good luck charms were seized after the new gambling law.",
        "Thank you, veterans.",
        "Beautiful Cross from #26 Samuel Fomin",
        "I love this song",
        "Anyone wanna join in?",
    ]
    for text in kept:
        assert pleasantry_reason({"text": text}) is None, text


def test_ingest_filter_drops_spam_and_pleasantry():
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


def test_planet_guard_after_label_uses_title_and_pleasantry_share():
    members = [{"text": "Thank you!"} for _ in range(8)] + [{"text": "Beautiful!"} for _ in range(2)]
    assert planet_chitchat_reason(members, [], name="Art Appreciation")
    assert planet_chitchat_reason([{"text": "x"}] * 23, [], name="Count")
    policy_members = [
        {
            "text": (
                "Twitch's new moderation policy will change how streamers handle politics "
                "on the platform during live broadcasts."
            )
        }
        for _ in range(6)
    ]
    assert planet_chitchat_reason(policy_members, [], name="Streaming Policy") is None


def test_fixture_target_planets_would_be_guarded_at_preview_sizes():
    fixture = _load_fixture()
    post_counts = {
        "global:Art Appreciation": 689,
        "global:Twitch Stream": 459,
        "Business:Count": 23,
        "Sports:Good Luck": 16,
        "Sports:Happy Anniversary": 21,
        "Education:Course": 19,
        "Education:Full Agreement": 8,
        "Other:Art Appreciation": 645,
        "Other:the weekend": 85,
        "Other:Happy Birthday": 143,
    }
    for key, texts in fixture["target_planets"].items():
        name = key.split(":", 1)[1]
        members = [{"text": text} for text in texts]
        post_count = post_counts[key]
        expanded = members * max(1, post_count // max(len(members), 1))
        assert planet_chitchat_reason(expanded[:post_count], [], name=name), key


def test_ingest_block_reason_keeps_quality_claim():
    post = {"text": "The Senate should publish the mail ballot rules before November."}
    assert ingest_block_reason(post) is None
