"""Chit-chat guard: content filter and post-label planet guard (#208).

Planet titles are not an input. Target clusters come from the preview
representatives in tests/fixtures/chitchat_preview_posts.json.
"""

import json
from pathlib import Path

from pipeline.chitchat_guard import (
    PLEASANTRY_SHARE_DROP,
    ingest_block_reason,
    MODEL_CHITCHAT_SHARE_FLOOR,
    planet_chitchat_reason,
    pleasantry_reason,
    pleasantry_share,
)
from pipeline.free_ingest import keep_edition_quality
from pipeline.label import (
    build_planet_name_prompt,
    build_topic_prompt,
    chitchat_flag,
    label_topic,
    name_from_perspectives,
    parse_label,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "chitchat_preview_posts.json"

POST_COUNTS = {
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


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _members(texts: list[str]) -> list[dict]:
    return [{"text": text} for text in texts]


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
        "Anyone wanna join in?",
        "I LOVE that you LOVE and BELONG in diapers!!",
    ]
    for text in must_drop:
        assert pleasantry_reason({"text": text}) is not None, text
    # The diaper compliment is a real representative, not a synthetic line.
    diaper = [
        post["text"]
        for post in fixture["other_posts"]
        if "BELONG in diapers" in post["text"]
    ]
    assert diaper
    assert pleasantry_reason({"text": diaper[0]}) is not None


def test_preview_discourse_negatives_from_artifact_and_review():
    fixture = _load_fixture()
    by_fragment = {
        "art of betrayal": None,
        "I absolutely love this song": None,
        "powered by every day Canadians": None,
        "out-midfield Spain": None,
    }
    corpus = list(fixture["other_posts"])
    for texts in fixture["target_planets"].values():
        corpus.extend({"text": text} for text in texts)
    for post in corpus:
        for fragment in by_fragment:
            if fragment in post["text"] and by_fragment[fragment] is None:
                by_fragment[fragment] = post["text"]
    assert all(by_fragment.values()), by_fragment
    kept = list(by_fragment.values()) + [
        "The anniversary of the invasion is not a happy anniversary for Ukraine.",
        "Happy anniversary of the Voting Rights Act, which Congress still has to defend.",
        "Residents can watch live as the council votes on the housing bill tonight.",
        "The Senate Judiciary Committee is live now for the confirmation hearing on the nominee.",
        "C-SPAN is live now covering the House vote on the spending bill.",
        "We go live at noon when the governor signs the bill.",
        "The jobs report was amazing and wages finally rose.",
        "This court ruling is wonderful for renters.",
        "Good luck charms were seized after the new gambling law.",
        "Thank you, veterans.",
        "Beautiful Cross from #26 Samuel Fomin",
        "I love this song",
        "Ah well. I'm in Spain, I don't give a fuck.",
        "Twitch's new moderation policy will change how streamers handle politics on the platform.",
        "The algebra course still requires the calculus prerequisite and a statistics exam.",
        "The cup-final injury will keep the striker out of the championship.",
        "The county recount of the mail ballots is still in court.",
        "Love these~ The way you're dealing with the height difference here is fun too!",
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


def test_planet_guard_uses_post_share_not_the_title():
    fixture = _load_fixture()
    art = _members(fixture["target_planets"]["global:Art Appreciation"])
    for name in ("Art Appreciation", "Kind Words", "Sweet Thanks", None, ""):
        reason = planet_chitchat_reason(art, ["thanks", "cute"], name=name)
        assert reason, name
        assert "Art Appreciation" not in (reason or "")
        assert "Kind Words" not in (reason or "")
    # A real planet that only shares the name stays, including a pile of "x".
    algebra = [
        {"text": "The algebra course still requires the calculus prerequisite and a statistics exam."}
    ] * 19
    injury = [
        {"text": "The cup-final injury will keep the striker out of the championship after the tackle."}
    ] * 16
    recount = [{"text": "The county recount of the mail ballots is still in court after the election."}] * 23
    filler = [{"text": "x"}] * 23
    for members, stolen in (
        (algebra, "Course"),
        (injury, "Good Luck"),
        (recount, "Count"),
        (filler, "Count"),
    ):
        assert planet_chitchat_reason(members, [], name=stolen) is None, stolen
        assert planet_chitchat_reason(members, [], name="Kind Words") is None
    # A model yes does not drop a real topic planet. These posts are 0% pleasantry.
    assert pleasantry_share(algebra) == 0
    assert planet_chitchat_reason(algebra, [], name="Course", model_chitchat=True) is None
    assert planet_chitchat_reason(algebra, [], name="Course", model_chitchat=False) is None
    assert planet_chitchat_reason(algebra, [], name="Course", model_chitchat=None) is None
    # Fixture gap: real planets are 0%, and the only sub-55% pleasantry planets
    # are at 50%. 30% is that gap, so yes can drop the 50% mix and cannot drop 0%.
    mixed = [
        {"text": post["text"]}
        for post in fixture["other_posts"]
        if post["planet"] == "Character Appearance"
    ]
    mixed_share = pleasantry_share(mixed)
    assert MODEL_CHITCHAT_SHARE_FLOOR == 0.30
    assert MODEL_CHITCHAT_SHARE_FLOOR < mixed_share < PLEASANTRY_SHARE_DROP
    assert planet_chitchat_reason(mixed, [], model_chitchat=True)
    assert planet_chitchat_reason(mixed, [], model_chitchat=False) is None
    assert planet_chitchat_reason(mixed, [], model_chitchat=None) is None
    policy = [
        {
            "text": (
                "Twitch's new moderation policy will change how streamers handle politics "
                "on the platform during live broadcasts."
            )
        }
    ] * 6
    assert planet_chitchat_reason(policy, [], name="Streaming Policy") is None
    assert planet_chitchat_reason(policy, [], name="Twitch Stream") is None


def test_fixture_target_planets_drop_from_content_under_any_name():
    fixture = _load_fixture()
    for key, texts in fixture["target_planets"].items():
        members = _members(texts)
        share = pleasantry_share(members)
        assert share >= PLEASANTRY_SHARE_DROP, (key, share)
        post_count = POST_COUNTS[key]
        estimated_remaining = int(round(post_count * (1 - share)))
        for name in (key.split(":", 1)[1], "Kind Words", None):
            reason = planet_chitchat_reason(members, [], name=name)
            assert reason, (key, name)
        # The published size is not used to pad members. Share is the decision.
        assert estimated_remaining < post_count
        assert "x" not in texts


def test_ingest_block_reason_keeps_quality_claim():
    post = {"text": "The Senate should publish the mail ballot rules before November."}
    assert ingest_block_reason(post) is None
    assert ingest_block_reason({"text": "Thanks!!"}).startswith("chitchat:")


def test_naming_prompts_ask_chitchat_on_the_existing_call():
    prompt = build_topic_prompt([{"text": "Thanks!!", "likes": 1}], ["thanks"])
    rename = build_planet_name_prompt(
        [{"text": "Thanks!!", "likes": 1}],
        [{"title": "Thanks", "summary": "A thank you."}],
    )
    for text in (prompt, rename):
        assert '"chitchat": "yes or no"' in text
        assert "one-word agreement" in text
        assert "public topic" in text
    yes = parse_label(
        '{"name": "Thanks", "summary": "People are thanking each other.", "chitchat": "yes"}'
    )
    no = parse_label(
        '{"name": "Housing Bill", "summary": "The council votes on the housing bill.", "chitchat": "no"}'
    )
    absent = parse_label('{"name": "Housing Bill", "summary": "The council votes on the housing bill."}')
    assert yes["chitchat"] is True
    assert chitchat_flag(no) is False
    assert chitchat_flag(absent) is None
    assert "chitchat" not in absent


def test_existing_naming_call_keeps_the_flag_without_a_new_call():
    def generate(prompt):
        assert "chitchat" in prompt
        return '{"name": "Housing Bill", "summary": "The council votes on the housing bill.", "chitchat": "yes"}'

    labeled = label_topic(
        [{"text": "The council votes on the housing bill tonight.", "likes": 4}],
        ["housing", "bill"],
        generate=generate,
    )
    assert labeled["chitchat"] is True
    assert labeled["name"] == "Housing Bill"


def test_rename_call_returns_name_and_flag(monkeypatch):
    def _gen(_prompt, seed=None):
        del seed
        return '{"name": "Housing Bill", "chitchat": "yes"}'

    monkeypatch.setattr("pipeline.label._resolve_backend", lambda backend: "openai")
    monkeypatch.setattr("pipeline.label._generator_for", lambda chosen, model: _gen)
    name, flag = name_from_perspectives(
        [{"text": "The council votes on the housing bill tonight."}],
        [{"title": "Housing", "summary": "The council votes on the housing bill."}],
        ["housing", "bill"],
        backend="openai",
    )
    assert name == "Housing Bill"
    assert flag is True
    monkeypatch.setattr("pipeline.label._resolve_backend", lambda backend: "heuristic")
    assert name_from_perspectives(
        [{"text": "The council votes on the housing bill tonight."}],
        [{"title": "Housing", "summary": "The council votes."}],
        ["housing"],
        backend="heuristic",
    ) == (None, None)
