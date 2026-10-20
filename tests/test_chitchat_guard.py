"""Chit-chat guard: content filter and post-label planet guard (#208).

Planet titles are not an input. Target clusters come from the preview
representatives in tests/fixtures/chitchat_preview_posts.json.
"""

import json
from pathlib import Path

from pipeline.chitchat_guard import (
    PLEASANTRY_SHARE_DROP,
    clustering_topup_shortfall,
    edition_posts_for_clustering,
    ingest_block_reason,
    is_bare_link_post,
    MODEL_CHITCHAT_SHARE_FLOOR,
    planet_chitchat_reason,
    pleasantry_reason,
    pleasantry_share,
)
from scripts.replay_planet_guard import classify_planet
from pipeline.free_ingest import keep_edition_quality
from pipeline.language import edition_filter_reason
from pipeline.store import should_drop_stored_post
from pipeline.label import (
    build_planet_name_prompt,
    build_topic_prompt,
    chitchat_flag,
    label_topic,
    name_from_perspectives,
    parse_label,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "chitchat_preview_posts.json"
LEAKED = Path(__file__).resolve().parent / "fixtures" / "chitchat_leaked_planets.json"
REPLAY = Path(__file__).resolve().parent / "fixtures" / "chitchat_replay_39072480258.json"

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
        "👀",
        "!!!",
        "Toof",
        "My Uber is here",
        "It's officially my 30th birthday party today",
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
        "Yeah I would honestly be hyped if a friend of mine threw one of these and I’d bring a gift. But why are you, as a grown man, feeling competitive about a child’s birthday??",
        "Uber drivers went on strike over wages.",
        "Impeach Hegseth.",
        "We, of course, are leaving out numerous other revenue sources from this. Toys/merch, streaming, etc. Also excluding multiple superhero films.",
        "Keep out of prison even if most Israelis die. Netanyahu has port-a-potty bomb shelters. www.youtube.com/live/0IVuVK6",
        "Hegseth does need to be impeached. The live stream execution idea.",
        "little vent but with all the anti trans stuff happening i hate that i now live in constant fear",
        "Coleman Owen will factor into punt returns for the Packers this week. www.youtube.com/live/EEZnyBF",
        "https://example.com/story",
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
    # A real planet that only shares the name stays. A pile of "x" is a one-word reply.
    algebra = [
        {"text": "The algebra course still requires the calculus prerequisite and a statistics exam."}
    ] * 19
    injury = [
        {"text": "The cup-final injury will keep the striker out of the championship after the tackle."}
    ] * 16
    recount = [{"text": "The county recount of the mail ballots is still in court after the election."}] * 23
    for members, stolen in (
        (algebra, "Course"),
        (injury, "Good Luck"),
        (recount, "Count"),
    ):
        assert planet_chitchat_reason(members, [], name=stolen) is None, stolen
        assert planet_chitchat_reason(members, [], name="Kind Words") is None
    # One-word replies are pleasantries. The name Count is not what drops them.
    filler = [{"text": "x"}] * 23
    assert planet_chitchat_reason(filler, [], name="Count")
    assert planet_chitchat_reason(filler, [], name="Kind Words")
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


def test_preview_39065623599_leaked_planets_drop_from_content():
    """Representatives from the run where the guard published these three.

    Full member texts are not in the artifact. Uber stores one representative
    for ten posts. The guard uses every member it is given, and these
    representative mixes are each at least 55% chit-chat under any name.
    """
    leaked = json.loads(LEAKED.read_text(encoding="utf-8"))
    for key, planet in leaked["planets"].items():
        members = _members(planet["texts"])
        share = pleasantry_share(members)
        assert share >= PLEASANTRY_SHARE_DROP, (key, share)
        assert planet_chitchat_reason(members, [], name="Kind Words"), key
        assert planet_chitchat_reason(members, [], name=None), key


def test_chitchat_drop_frees_the_catalog_slot_for_the_next_candidate():
    """The free-ingest catalog keeps drafting until ``keep`` planets survive."""
    import numpy as np

    from pipeline import live
    from tests.test_faces_53 import _blobs

    def group(text: str, prefix: str, seed: int, count: int = 12):
        matrix = _blobs([count], seed=seed)
        posts = [
            {
                "uri": f"at://{prefix}/{index}",
                "author": f"{prefix}.{index}",
                "clean_text": text,
                "text": text,
                "likes": 1,
            }
            for index in range(count)
        ]
        return posts, matrix

    groups = [
        group("My Uber is here", "uber", 1),
        group("The city council should vote on the housing bill and rent control this month.", "house", 2),
    ]
    posts, blocks, topics = [], [], []
    for index, (group_posts, matrix) in enumerate(groups):
        start = len(posts)
        posts.extend(group_posts)
        blocks.append(matrix)
        topics.append(
            {
                "id": index,
                "size": len(group_posts),
                "member_indices": list(range(start, len(posts))),
                "terms": [group_posts[0]["text"].split()[0]],
            }
        )
    clustered = {
        "topics": topics,
        "matrix": np.vstack(blocks),
        "assignments": [],
        "noise_count": 0,
    }
    settings = {"label_backend": "heuristic", "representative_posts": 6, "seed": 0, "min_cluster_size": 5}
    built, _membership, _faces = live._build_topics(posts, clustered, settings, keep=1)
    assert len(built) == 1
    assert "uber" not in built[0]["name"].lower()
    assert "bill" in built[0]["name"].lower() or "housing" in built[0]["name"].lower() or "council" in built[0]["name"].lower()


def test_get_well_wishes_and_personal_health_updates_drop():
    """Directed wishes and the author's own illness journal are removed.

    A hospital story, a staffing policy, or a healthcare argument stays.
    The planet title is not what drops a journal planet.
    """
    wishes = [
        "Oh I am sorry to hear this. Wishing you a speedy and full recovery.",
        "Hoping for a speedy recovery!",
        "Despite it, I'm wishing you a speedy recovery.",
        "so glad it went okay!! i hope she has a speedy recovery!!",
        "For a quick recovery, rest in bed to restore your strength.",
        "Hope you feel better soon",
        "i genuinely do hope that you feel better in the morning",
        "Sending healing purrs to you as well.",
        "prayers for you",
        "Get well soon",
    ]
    journals = [
        "I've been sick all week.",
        "Just got back from the hospital.",
        "I'm feeling so much better today! Still wiped and tired, but the migraine has passed.",
        "It is a lie to tell myself that I will ever be fully recovered from chemo, but some things will return in time.",
        "I feel so sick and ill right now. Why is this happening to me?",
        "I am medicated up at this point and feeling better.",
    ]
    stays = [
        "The senator was admitted to the hospital after the illness was reported.",
        "Hospital policy now covers recovery time after surgery for the nurses.",
        "The measles outbreak closed two schools after new cases were reported.",
        "Medicare should cover hospital stays after surgery.",
        "I feel sick about the new tariffs.",
        "I'm sick of Congress missing the healthcare vote.",
        "got a haircut y'all",
        "new haircut with limited edition color",
        "The cup-final injury will keep the striker out of the championship.",
    ]
    for text in wishes:
        assert pleasantry_reason({"text": text}) == "wish", text
    for text in journals:
        assert pleasantry_reason({"text": text}) == "health_update", text
        assert ingest_block_reason({"text": text}) == "chitchat:health_update", text
    for text in stays:
        assert pleasantry_reason({"text": text}) is None, text
    wish_planet = [{"text": "Hope you feel better soon"}] * 6
    assert planet_chitchat_reason(wish_planet, [], name="Health Issues")
    assert planet_chitchat_reason(wish_planet, [], name="Kind Words")
    journal_planet = [
        {"text": "I've been sick all week and I am still home from the hospital."}
    ] * 6
    assert planet_chitchat_reason(journal_planet, [], name="Health Issues")
    assert planet_chitchat_reason(journal_planet, [], name="Kind Words")
    chemo = [
        {
            "text": (
                "It is a lie to tell myself that I will ever be fully recovered from chemo, "
                "but some things will return in time."
            )
        }
    ] * 6
    assert planet_chitchat_reason(chemo, [], name="Recovering Health")
    # Mostly journals or wishes drops. A minority does not, and the title cannot.
    mixed_drop = [
        {"text": "I've been sick all week."},
        {"text": "Just got back from the hospital."},
        {"text": "Hope you feel better soon"},
        {"text": "I am medicated up at this point and feeling better."},
        {"text": "The measles outbreak closed two schools after new cases were reported."},
        {"text": "Medicare should cover hospital stays after surgery."},
    ]
    assert planet_chitchat_reason(mixed_drop, [], name="Health Issues")
    mixed_keep = [
        {"text": "I've been sick all week."},
        {"text": "The senator was admitted to the hospital after the illness was reported."},
        {"text": "Hospital policy now covers recovery time after surgery for the nurses."},
        {"text": "The measles outbreak closed two schools after new cases were reported."},
        {"text": "Medicare should cover hospital stays after surgery."},
        {"text": "Healthcare in the US is tied to employment and the insurance industry."},
    ]
    assert planet_chitchat_reason(mixed_keep, [], name="Health Issues") is None
    kept, blocked_spam, blocked_other = keep_edition_quality(
        [
            {"uri": "at://news", "text": "The measles outbreak closed two schools after new cases were reported."},
            {"uri": "at://sick", "text": "I've been sick all week."},
            {"uri": "at://back", "text": "Just got back from the hospital."},
        ]
    )
    assert [post["uri"] for post in kept] == ["at://news"]
    assert blocked_spam == 0
    assert blocked_other == 2


def test_issue_227_thank_planet_201_mention_cluster_drops():
    """Published Thank ball (~201 posts): many thank mentions, few ingest thanks."""
    filler = {
        "text": "The housing council meets Tuesday about zoning changes downtown.",
    }
    mention = {
        "text": (
            "I want to thank everyone who came out to support the local "
            "fundraiser last night."
        ),
    }
    members = [mention] * 65 + [filler] * (201 - 65)
    reason = planet_chitchat_reason(members, [], name="Thank")
    assert reason is not None
    assert "mention thanks" in reason
    assert "65 posts" in reason


def test_issue_227_twitch_planet_55_bare_link_cards_drop():
    """Published ~55-post twitch.tv ball (review: 15/55 stream share, still kept).

    Link cards keep the URL in ``clean_text`` while ``text`` is whitespace.
    Salient term ``twitch`` names the ball; channel slugs stay below the cutoff.
    """
    link_card = {"text": " ", "clean_text": "twitch.tv/48291"}
    text_url = {"text": "twitch.tv/71024"}
    members = [link_card] * 39 + [text_url] * 16
    assert len(members) == 55
    reason = planet_chitchat_reason(members, [], name="Twitch")
    assert reason == "Mostly about a streaming platform, not a topic"


def test_stream_cluster_keeps_topical_news_planets():
    """Ukraine, vote, Israel, trans, healthcare, fascism, and Trump/Musk must not drop."""
    fillers = {
        "ukraine": "The anniversary of the invasion is not a happy anniversary for Ukraine.",
        "trump": "Trump and Musk argued over tariffs and Ukraine aid in a televised interview.",
        "vote": "The Senate should publish the mail ballot rules before November.",
        "israel": (
            "Keep out of prison even if most Israelis die. Netanyahu has port-a-potty "
            "bomb shelters. www.youtube.com/live/0IVuVK6"
        ),
        "trans": (
            "little vent but with all the anti trans stuff happening i hate that i now "
            "live in constant fear"
        ),
        "healthcare": "I'm sick of Congress missing the healthcare vote.",
        "fascism": "We cannot let fascism take root in our local school boards.",
    }
    for name, text in fillers.items():
        members = [{"text": text}] * 55
        assert planet_chitchat_reason(members, [], name=name) is None


def test_twitch_policy_planet_55_stays():
    policy = {
        "text": (
            "Twitch's new moderation policy will change how streamers handle politics "
            "on the platform during live broadcasts."
        ),
    }
    filler = {
        "text": "Congress debated the spending package late into the evening on Thursday.",
    }
    members = [policy] * 8 + [filler] * 47
    assert planet_chitchat_reason(members, [], name="Streaming Policy") is None


def test_issue_227_production_thank_planet_samples():
    """Exact lines from the #224 reviewer sample of the Thank planet (622 posts)."""
    drops = [
        "Thank you so much ^^u^^ we're gradually getting back into the swing of things with it",
        "My pleasure, Kate. I'll keep the lights on for you.",
        "Your work in progress pics are always incredible!",
        "Of course! Thank you for making an awesome shirt!",
        "Thanks! lots of photogenic ones today.",
    ]
    for text in drops:
        assert pleasantry_reason({"text": text}) is not None, text
    assert pleasantry_reason({"text": "Thank you, Senator, for voting no on the bill."}) is None
    assert pleasantry_reason({"text": "How can I contribute to this great work?"}) is None


def test_issue_227_reviewer_false_positive_keeps():
    """Topical posts from the bc-88ba023c hand sample must stay."""
    keeps = [
        "Thank you - never forget. The only people who support nazis... are nazis.",
        "I voted today, and it feels so good! #IVoted",
        (
            "Great - they are scumbag organizations… if you/your staff has used AI for the photo "
            "to please not. It is destroying communities, the environment, & is built on stolen work."
        ),
        (
            "Webtoon vs ComicFury vs Itch vs Tumblr — find your audience. "
            "Great for posting ebooks and building a readership."
        ),
        (
            "I can't do treatments. Anytime a studio hires me to write a screenplay "
            "I end up rewriting the whole thing."
        ),
    ]
    for text in keeps:
        assert pleasantry_reason({"text": text}) is None, text


def test_issue_227_missed_shapes_and_topical_lookalikes():
    drops = [
        "THIS IS SO GOOD",
        "this is so good 🤩",
        "This is so good.",
        "Wonderful design and rendering!! Love his soft eyes",
        "Omg look how cute this is!!",
        "Karaoke stream! Join me",
        "I appreciate all the support on here",
    ]
    for text in drops:
        assert pleasantry_reason({"text": text}) is not None, text
    keeps = [
        "Thank you, Senator, for voting no on the bill.",
        "Twitch's new moderation policy will change how streamers handle politics on the platform.",
        "The Senate Judiciary Committee is live now for the confirmation hearing on the nominee.",
        "The jobs report was amazing and wages finally rose.",
    ]
    for text in keeps:
        assert pleasantry_reason({"text": text}) is None, text
    thank_thread = [{"text": "Thank you!!"}] * 8 + [{"text": "Thanks so much!"}] * 10
    assert planet_chitchat_reason(thank_thread, [], name="Thank You")
    policy = [
        {
            "text": (
                "Twitch's new moderation policy will change how streamers handle politics "
                "on the platform during live broadcasts."
            )
        }
    ] * 6
    assert planet_chitchat_reason(policy, [], name="Thank You") is None


def test_hashtags_sports_jabs_and_stream_mentions_stay():
    stays = [
        "#NoKings❌👑",
        "Well, congratulations, Auburn. Looks like after today y'all will have still been us exactly as many times as Georgia Tech has over the last 10 games.",
        "Forgive me for my dumb complaint, but with 500 streaming channels it should be easier to find full holiday cartoon eps like Yogi Bear.",
        "I'm so pissed that it is not scheduled here, so I probably have to wait until it goes to streaming.",
        "My camera is mainly setup for streaming, which adds steps before I can use it.",
        "NYC Bar is still the theme of the stream.",
        "We didn't finish the RP, but I worked on it during my art stream the other day.",
        "I'm losing enthusiasm to stream tonight but I really need to.",
        "the war never ends until those dicks are gone so neither can I rest in the fields of fictional combat Why? Because why I can't act independently, I can share that this era isn't unique. www.twitch.tv/mayonaka_mid",
    ]
    drops = [
        "I'm live on joystick.tv today",
        "It's time to stream",
        "Come through for the Saturday game twitch.tv/awingedshield",
        "www.twitch.tv/gamecobra Time to start some deadlock!",
        "HE'S MARIOING IT OH MY GOD www.twitch.tv/yeah_sure82",
        "I’m streaming youtu.be/DUBlSZQzSlc",
        "1UpWar is LIVE on Twitch! Watch now: https://www.twitch.tv/1upwar",
    ]
    for text in stays:
        assert pleasantry_reason({"text": text}) is None, text
    for text in drops:
        assert pleasantry_reason({"text": text}) == "stream_announce", text


def test_bare_youtube_link_counts_in_the_planet_share_only():
    bare = {"text": "youtu.be/VAWjsVoDpm0 #musicsky"}
    assert pleasantry_reason(bare) is None
    assert is_bare_link_post(bare)
    assert ingest_block_reason(bare) == "link_only"
    assert planet_chitchat_reason([bare] * 8, [], name="Music Videos")
    sentence = {"text": "You might find this video heartening. youtu.be/SOSOyr1yPao"}
    assert not is_bare_link_post(sentence)
    assert planet_chitchat_reason([sentence] * 8, [], name="Music Videos") is None


def test_stored_drop_and_clustering_agree_on_raw_text_not_stale_clean_text(monkeypatch):
    """#219 stored rows may have ``clean_text`` without the URL; clustering must match ingest."""

    monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)

    def assert_edition_matches_ingest(post: dict) -> None:
        block = ingest_block_reason(post)
        edition = edition_filter_reason(post)
        assert edition == block
        kept, language, links, chitchat = edition_posts_for_clustering([post])
        if block in {"link_only", "language"}:
            assert len(kept) == 0
            assert should_drop_stored_post(post) is False
        elif block is None:
            assert len(kept) == 1
        else:
            assert len(kept) == 0

    commentary = {
        "uri": "at://stored/commentary-link",
        "text": "There it is!! bsky.app/profile/example.bsky.social/post/abc",
        "clean_text": "There it is!!",
    }
    assert edition_filter_reason(commentary) is None
    assert_edition_matches_ingest(commentary)

    stale_bare = {
        "uri": "at://stored/bare-youtube",
        "text": "youtu.be/VAWjsVoDpm0 #musicsky",
        "clean_text": "#musicsky",
    }
    assert edition_filter_reason(stale_bare) == "link_only"
    assert ingest_block_reason(stale_bare) == "link_only"
    assert_edition_matches_ingest(stale_bare)


def test_clustering_pass_counts_carried_over_skips():
    carried = {"at://old-thanks", "at://old-link"}
    posts = [
        {
            "uri": "at://old-thanks",
            "text": "Thanks!!",
            "clean_text": "Thanks!!",
        },
        {
            "uri": "at://old-link",
            "text": "https://example.com/only",
            "clean_text": "https://example.com/only",
        },
        {
            "uri": "at://fresh",
            "text": "The senate should vote on the housing bill before Friday.",
            "clean_text": "The senate should vote on the housing bill before Friday.",
        },
    ]
    carried_skips: dict[str, int] = {}
    kept, language, links, chitchat = edition_posts_for_clustering(
        posts,
        carried_uris=carried,
        carried_skips=carried_skips,
    )
    assert [post["uri"] for post in kept] == ["at://fresh"]
    assert (language, links, chitchat) == (0, 1, 1)
    assert carried_skips == {"link_only": 1, "chitchat": 1}


def test_link_and_language_switch_matches_main_on_the_clustering_path(monkeypatch):
    """Main already skipped these posts before clustering and still stored them.

    ``partition_posts`` is on main (live.py, since 322b12f). Free ingest there
    counted link-only and non-English posts in the corpus. ``=0`` does that.
    ``=1`` also refuses them at ingest so they do not count toward the 100K.
    Neither setting clusters them.
    """
    senate = {"text": "The senate should vote on the housing bill before Friday."}
    link = {"text": "https://example.com/only"}
    dutch = {"text": "Het is niet een goed plan want de regering heeft geen meerderheid."}
    thanks = {"text": "Thanks!!"}
    posts = [senate, link, dutch, thanks]

    def clustered():
        kept, language, links, chitchat = edition_posts_for_clustering(posts)
        return [post["text"] for post in kept], language, links, chitchat

    monkeypatch.delenv("DROP_LINK_AND_LANGUAGE_AT_INGEST", raising=False)
    kept, language, links, chitchat = clustered()
    assert kept == [senate["text"]]
    assert (language, links, chitchat) == (1, 1, 1)
    assert ingest_block_reason(link) == "link_only"
    assert ingest_block_reason(dutch) == "language"
    # Switch on: the clustering gap is a shortfall, because these posts
    # do not count toward the stored edition.
    assert clustering_topup_shortfall(10, 7, skipped_language=2, skipped_links=1) == 3

    monkeypatch.setenv("DROP_LINK_AND_LANGUAGE_AT_INGEST", "0")
    kept, language, links, chitchat = clustered()
    assert kept == [senate["text"]]
    assert (language, links, chitchat) == (1, 1, 1)
    assert ingest_block_reason(link) is None
    assert ingest_block_reason(dutch) is None
    assert ingest_block_reason(thanks).startswith("chitchat:")
    # Switch off is main: the three excluded posts already filled the corpus,
    # so clustering does not ask ingest to replace them. Chit-chat still does.
    assert clustering_topup_shortfall(10, 7, skipped_language=2, skipped_links=1) == 0
    assert clustering_topup_shortfall(10, 7, skipped_language=0, skipped_links=0) == 3


def test_replay_39072480258_representatives():
    """Saved planets from preview 39072480258.

    Speedy Recovery's representatives are recovery wishes. Health Issues and
    Recovering Health are mostly personal illness journals plus those wishes,
    so they drop too. US Healthcare is a policy argument and stays. The title
    is not the input.
    """
    payload = json.loads(REPLAY.read_text(encoding="utf-8"))
    rows = [
        classify_planet(planet["section"], planet["name"], planet["texts"], planet["post_count"])
        for planet in payload["planets"]
    ]
    dropped = [(row["section"], row["name"]) for row in rows if row["decision"] == "DROP"]
    assert dropped == [
        ("Health", "Health Issues"),
        ("Health", "Speedy Recovery"),
        ("Health", "Recovering Health"),
    ]
    by_name = {(row["section"], row["name"]): row for row in rows}
    speedy = by_name[("Health", "Speedy Recovery")]
    assert speedy["share"] == 1
    assert planet_chitchat_reason(
        [{"text": text} for text in _planet_texts(payload, "Health", "Speedy Recovery")],
        [],
        name="Kind Words",
    )
    issues = by_name[("Health", "Health Issues")]
    assert issues["share"] >= PLEASANTRY_SHARE_DROP
    recovering = by_name[("Health", "Recovering Health")]
    assert recovering["share"] >= PLEASANTRY_SHARE_DROP
    for section, name in (
        ("Other", "New Haircuts"),
        ("global", "Music Videos"),
        ("Culture", "Music Videos"),
        ("Health", "US Healthcare"),
        ("Health", "Eating Issues"),
        ("Other", "Sleep Issues"),
        ("Education", "School Medication Policy"),
    ):
        assert by_name[(section, name)]["decision"] == "KEEP"
        assert by_name[(section, name)]["share"] < PLEASANTRY_SHARE_DROP


def _planet_texts(payload: dict, section: str, name: str) -> list[str]:
    for planet in payload["planets"]:
        if planet["section"] == section and planet["name"] == name:
            return list(planet["texts"])
    raise AssertionError(f"missing {section}:{name}")


def test_issue_208_good_morning_greeting_variants():
    """Live miss 2026-10-19: Good Morning planet (#208 comment)."""
    greetings = [
        "Good morning to you!",
        "Good morning from",
        "Good morning from Kinmo the cat.",
        "Hiya Baron! Good morning to you.",
        "Morning Richard, how are you? Xx",
        "Good morning Susan, make it a good day.",
        "Every Morning is a Good Morning…",
    ]
    for text in greetings:
        assert pleasantry_reason({"text": text}) == "greeting", text
    keeps = [
        "The Senate met this morning to debate the healthcare bill.",
        "Good morning! Protect Trans Kids",
    ]
    for text in keeps:
        assert pleasantry_reason({"text": text}) is None, text


def test_issue_208_good_morning_planet_representatives_drop():
    """Fifteen published Good Morning representatives must hit the planet guard."""
    reps = [
        "Good morning to you!",
        "Good morning from Kinmo the cat.",
        "Hiya Baron! Good morning to you.",
        "Morning Richard, how are you? Xx",
        "Good morning Susan, make it a good day.",
        "Every Morning is a Good Morning…",
        "Good morning to you!",
        "Good morning from",
        "Good morning!",
        "Morning!",
        "Good morning friend!",
        "Good morning everyone!",
        "Good morning beautiful!",
        "Good morning to you too!",
        "Good morning! Protect Trans Kids",
    ]
    members = _members(reps)
    share = sum(1 for m in members if pleasantry_reason(m)) / len(members)
    assert share >= PLEASANTRY_SHARE_DROP
    assert planet_chitchat_reason(members, [], name="Good Morning") is not None


def test_issue_208_morning_patterns_do_not_swallow_topics():
    """Reviewer strings (bc-44865100) for #208 greeting guard, verbatim."""
    must_catch = [
        "Good morning everyone, have a great day ☀️",
        "Good morning to you!",
        "Morning Richard, how are you? Xx",
        "Good morning Susan, make it a good day.",
        "Good morning from Kinmo the cat.",
        "Good morning from",
        "Hiya Baron! Good morning to you.",
        "Every Morning is a Good Morning…",
        "Good morning, I hope everyone sleeps well",
        "Good morning all, peaceful vibes today",
        "Morning friends, enjoy your coffee",
        "Good morning dear, sleep well",
        "Good morning everyone, stay warm",
        "Good night, sweet dreams",
        "Good morning folks, coffee is on",
        "Good morning, I hope your day is easy",
    ]
    for text in must_catch:
        assert pleasantry_reason({"text": text}) == "greeting", text
    keeps = [
        # Original 16 (a31e73d)
        "Morning Joe said viewers loved the opening interview.",
        "Morning commute was brutal today",
        "good morning america interview with the coach",
        "Morning after pill ban",
        "Morning after pill access expands",
        "Good morning, the Lakers won",
        "Good morning! The Yankees won again",
        "Good afternoon, the Fed held rates steady",
        "Good night at the museum, the new exhibit opens Friday",
        "You are so far out of touch, I'm just not going to waste anymore time. Have a good evening.",
        "Good morning! Black Lives Matter",
        "Good morning! Free Palestine",
        "Good morning world news: talks stalled",
        "A good morning run before the marathon",
        "Morning after the game the coach resigned",
        "Good night folks, see you at the rally tomorrow",
        # Nine news-tail keeps (77ed247)
        "Good morning, I hope the bill passes",
        "Good morning, I hope the strike ends",
        "Good evening, I hope the senate confirms the judge",
        "Good afternoon, I hope the hurricane turns offshore",
        "Good morning, the peaceful protest grew overnight",
        "Good morning, my friend the senator spoke",
        "Good morning, enjoy your indictment",
        "Good morning, I hope Congress votes tonight",
        "Good morning, I hope Ukraine holds the line",
        # Fourteen fresh topic probes (bc-44865100, exact wording)
        "Good morning, I hope my landlord fixes the heat",
        "Good morning, enjoy the eclipse today",
        "Good morning, I hope the vaccine works",
        "Good morning, the tariffs start today",
        "Good evening, I hope my landlord fixes the heat",
        "Good morning, the parade starts at noon",
        "Good morning, I hope the train is on time",
        "Good afternoon, the bakery on Main burned",
        "Good morning, the bridge is closed for repairs",
        "Good evening, the aurora is visible tonight",
        "Good morning, I hope the recital sells out",
        "Good morning, the ferry is cancelled",
        "Good morning, enjoy the comet tonight",
        "Good morning, the choir concert sold out",
        "Good morning, I hope the Wi-Fi comes back",
        # Eleven vocabulary probes kept (b66dc85)
        "Good morning, coffee prices doubled",
        "Good morning, warm weather records broken in Texas",
        "Morning friends, the coffee shop union won",
        "Good night, the heat wave continues",
        "Good morning, the tea harvest is late",
        "Good morning, warmer oceans are bleaching the reef",
        "Good morning, rest stops closed on the highway",
        "Morning friends, coffee futures jumped overnight",
        "Good morning, stay orders halted the project",
        "Good morning, easy money flooded the market",
        "Good morning, sweet potato harvest failed",
        # Seven judgment / headline tails (d446d06 re-review, exact wording)
        "Good morning, Ozempic shortage",
        "Good morning, Bitcoin crashed",
        "Good morning, Moderna recalled",
        "Good morning Taylor Swift",
        "Good evening Hezbollah",
        "Good night Kamala",
        "Good morning Iran",
        # Seven wish-phrase + topic tails (b66dc85 re-review)
        "Good morning, I hope everyone sleeps through the storm warning",
        "Good morning, coffee is on sale downtown",
        "Good morning, enjoy your coffee before the hearing",
        "Good morning, I hope everyone sleeps through the eclipse",
        "Good morning, peaceful vibes before the parade",
        "Good night, sweet dreams about the merger",
        "Good morning, sleep well before the launch",
        # Nice-to-catch: no daypart open; must stay kept
        "Have a wonderful morning everyone",
    ]
    misclassified = []
    for text in keeps:
        reason = pleasantry_reason({"text": text})
        if reason is not None:
            misclassified.append(f"{reason}: {text}")
    assert misclassified == [], "\n".join(misclassified)
