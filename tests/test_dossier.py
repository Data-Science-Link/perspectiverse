"""Private dossiers: off by default, fixture model only, no public leak."""

from __future__ import annotations

import json
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

import pytest

from pipeline.briefs import sentences
from pipeline.dossier import (
    DOSSIER_ALLOWANCE_SUPERSEDED_USD,
    DOSSIER_NIGHTLY_BUDGET_USD,
    DOSSIER_OUTPUT_TOKENS_4PAGE,
    DOSSIER_PROMPT_VERSION,
    DOSSIER_RUN_RESERVE_USD,
    DossierBudget,
    MemoryDossierStore,
    allowance_fit,
    apply_dossiers,
    apply_dossiers_batch,
    assert_dossier_key,
    dossier_allowance_usd,
    dossier_night_budget,
    draw_summary_sample,
    quality_report,
    edition_markdown_key,
    enforce_no_repeat,
    estimate_tokens,
    extractive_dossier,
    index_key,
    load_retrieval_pack,
    main,
    needs_rebuild,
    price_tokens,
    project_nightly,
    project_pair,
    sample_posts,
    _same_sentence,
)
from pipeline.r2 import assert_dossier_key as r2_assert_dossier_key
from pipeline.settings import load_settings

EDITION = "2026-10-18"
SUMMARY = "Allies of the negotiators are named in the oil talks."
BRIEF = (
    "Allies of the negotiators are named in the oil talks. "
    "The posts question whether the talks help Ukraine at all. "
    "A quoted post names Kushner in the thread. "
    "The sample cites one news link in the text."
)
DETAIL = (
    "Allies of the negotiators are named in the oil talks.\n\n"
    "The posts question whether the talks help Ukraine at all.\n\n"
    "A later paragraph is too short."
)
DOSSIER = """
## Subject
Russia Ukraine War is the subject of the posts in this sample.

## Main arguments
The posts argue the oil talks enrich people close to the negotiators.
A second line in the sample says the talks do not help people on the ground.
A third line says the appropriated aid was steered aside from Ukraine.

## Evidence and sources cited
One post cites a multibillion-dollar oil deal and names Kushner and Witkoff as the people in the room.

## Sub-camps
The posts in this view do not split into a second camp of their own.

## What the other side says
No post in this sample defends the oil talks or calls them a finished peace plan.

## Notable quotes
@karrieurbanist.bsky.social writes that the talks expanded to include an oil deal for the negotiators.

## What changed this week
The sample does not show a change from an earlier week in the dates that were provided.
""".strip() + "\n"


def _posts(n=10, likes_at=None):
    posts = []
    for index in range(n):
        likes = 20 - index if likes_at is None else likes_at(index)
        posts.append(
            {
                "uri": f"at://post/{index}",
                "author": f"user{index}.bsky.social",
                "text": (
                    f"Post {index} talks about the oil deal, the negotiators, "
                    f"and whether the talks help Ukraine."
                ),
                "likes": likes,
                "created_at": "2026-10-18T12:00:00Z",
            }
        )
    return posts


def _topic(posts=None):
    posts = list(posts or _posts())
    return {
        "id": 1,
        "name": "Russia Ukraine War",
        "category": "World",
        "summary": "Old planet summary that should be replaced.",
        "brief": "Old planet brief one. Old planet brief two. Old planet brief three.",
        "detail": (
            "Old planet paragraph one is long enough to stand.\n\n"
            "Old planet paragraph two is long enough to stand.\n\n"
            "Old planet paragraph three is long enough to stand."
        ),
        "_member_uris": [post["uri"] for post in posts],
        "perspectives": [
            {
                "id": "1A",
                "title": "Ukraine Oil Deal",
                "summary": "Old face summary that should be replaced.",
                "brief": "Old face brief one. Old face brief two. Old face brief three.",
                "detail": (
                    "Old face paragraph one is long enough to stand.\n\n"
                    "Old face paragraph two is long enough to stand.\n\n"
                    "Old face paragraph three is long enough to stand."
                ),
                "representative_posts": posts,
                "_face_member_uris": [post["uri"] for post in posts],
            }
        ],
    }


def _generate(prompts):
    def generate(prompt: str) -> str:
        prompts.append(prompt)
        if "internal briefing" in prompt:
            return DOSSIER
        if "reading-screen" in prompt:
            return json.dumps({"summary": SUMMARY, "brief": BRIEF, "detail": DETAIL})
        raise AssertionError(prompt[:80])

    return generate


def _assert_tiers(text_summary: str, brief: str, detail: str):
    assert len(sentences(text_summary)) == 1
    brief_sentences = sentences(brief)
    assert 3 <= len(brief_sentences) <= 5
    assert not any(_same_sentence(text_summary, sentence) for sentence in brief_sentences)
    parts = [part.strip() for part in detail.split("\n\n") if part.strip()]
    assert len(parts) == 3
    assert all(len(part) >= 40 for part in parts)
    for part in parts:
        for sentence in sentences(part):
            assert not _same_sentence(sentence, text_summary)
            assert not any(_same_sentence(sentence, brief_sentence) for brief_sentence in brief_sentences)


def test_switch_defaults_off(monkeypatch, tmp_path):
    monkeypatch.delenv("PERSPECTIVERSE_DOSSIERS", raising=False)
    config = tmp_path / "pipeline.yaml"
    config.write_text("seed: 0\n", encoding="utf-8")
    assert load_settings(config)["dossiers"] is False
    monkeypatch.setenv("PERSPECTIVERSE_DOSSIERS", "1")
    assert load_settings(config)["dossiers"] is True
    monkeypatch.setenv("PERSPECTIVERSE_DOSSIERS", "0")
    assert load_settings(config)["dossiers"] is False


def test_missing_store_does_not_call_the_model():
    topic = _topic()
    before = topic["perspectives"][0]["summary"]
    called = []
    apply_dossiers(topic, _posts(), generate=lambda prompt: called.append(prompt), store=None, edition=EDITION)
    assert called == []
    assert topic["perspectives"][0]["summary"] == before
    assert "_dossier_action" not in topic


def test_fixture_model_stores_private_markdown_and_splits_tiers():
    posts = _posts()
    topic = _topic(posts)
    prompts = []
    store = MemoryDossierStore()
    apply_dossiers(topic, posts, generate=_generate(prompts), store=store, edition=EDITION)
    assert len(prompts) == 4
    assert all("dossiers/" not in json.dumps(topic) for _ in [0])
    blob = json.dumps(topic)
    assert "dossiers/" not in blob
    assert "## Notable quotes" not in blob
    assert "_dossier_action" not in blob
    assert "_member_uris" in topic
    face = topic["perspectives"][0]
    _assert_tiers(face["summary"], face["brief"], face["detail"])
    _assert_tiers(topic["summary"], topic["brief"], topic["detail"])
    assert not _same_sentence(topic["summary"], face["summary"])
    assert not any(_same_sentence(topic["summary"], sentence) for sentence in sentences(face["brief"]))
    markdown = store.get_text(edition_markdown_key(EDITION, 1, "1A"))
    assert markdown and "## Notable quotes" in markdown
    assert "@karrieurbanist.bsky.social" in markdown
    planet_key = edition_markdown_key(EDITION, 1)
    assert store.get_text(planet_key)
    pack = load_retrieval_pack(store, EDITION, 1, "1A")
    assert pack["markdown"].startswith("## Subject") or "## Subject" in pack["markdown"]
    assert pack["top_n"]
    assert "public/" not in planet_key
    again = len(prompts)
    apply_dossiers(topic, posts, generate=_generate(prompts), store=store, edition=EDITION)
    assert len(prompts) == again


def test_rebuild_threshold_and_top_n_floor():
    stored = {
        "prompt_version": DOSSIER_PROMPT_VERSION,
        "summary": "One sentence.",
        "brief": "Second sentence here. Third sentence here. Fourth sentence here.",
        "detail": "Paragraph one is long enough.\n\nParagraph two is long enough.\n\nParagraph three is long enough.",
        "post_uris": [f"u{index}" for index in range(10)],
        "top_n": [{"uri": f"u{index}", "likes": 10 - index} for index in range(8)],
    }
    same_top = stored["top_n"]
    exactly = [f"u{index}" for index in range(8)] + ["n1", "n2"]
    assert needs_rebuild(stored, exactly, same_top) is False
    over = [f"u{index}" for index in range(7)] + ["n1", "n2", "n3"]
    assert needs_rebuild(stored, over, same_top) is True
    climbed = [{"uri": "new", "likes": 50}] + stored["top_n"][:7]
    assert needs_rebuild(stored, stored["post_uris"], climbed) is True
    floor = min(item["likes"] for item in stored["top_n"])
    tied = [{"uri": "new", "likes": floor}] + stored["top_n"][:7]
    assert needs_rebuild(stored, stored["post_uris"], tied) is False
    stale = dict(stored, prompt_version="0")
    assert needs_rebuild(stale, stored["post_uris"], same_top) is True
    assert needs_rebuild(None, stored["post_uris"], same_top) is True


def test_enforce_no_repeat_fills_from_later_sections():
    reader = enforce_no_repeat(
        summary=SUMMARY,
        brief=BRIEF,
        detail=DETAIL,
        dossier=DOSSIER,
        forbidden=(),
        posts=_posts(3),
        title="Ukraine Oil Deal",
    )
    _assert_tiers(reader["summary"], reader["brief"], reader["detail"])
    assert _same_sentence(reader["summary"], SUMMARY)


def test_extractive_outline_uses_real_handles_and_no_model():
    posts = [
        {
            "author": "karrieurbanist.bsky.social",
            "text": "The talks expanded to an oil deal tied to the negotiators.",
            "likes": 18,
        },
        {
            "author": "bonjohnson.bsky.social",
            "text": "U.S.-Russia talks on Ukraine now involve an oil deal.",
            "likes": 4,
        },
    ]
    outline = extractive_dossier("planet", "Russia Ukraine War", posts, ["Ukraine Oil Deal"])
    for heading in (
        "Subject",
        "Main arguments",
        "Evidence and sources cited",
        "Sub-camps",
        "What the other side says",
        "Notable quotes",
        "What changed this week",
    ):
        assert f"## {heading}" in outline
    assert "@karrieurbanist.bsky.social" in outline
    assert "bonjohnson.bsky.social" in outline


def test_price_uses_the_repo_llama_rates():
    assert estimate_tokens("a" * 3600) == 1000
    assert price_tokens(1_000_000, 1_000_000) == Decimal("0.42000000")
    full = project_nightly(rebuild_fraction=1)
    assert project_nightly(rebuild_fraction=0)["usd"] == Decimal("0")
    fifth = project_nightly(rebuild_fraction="0.2")
    expected = (full["full_rebuild_usd"] * Decimal("0.2")).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )
    assert fifth["usd"] == expected
    assert full["usd"] > fifth["usd"] > 0
    assert full["planets"] == 110
    assert full["calls"] == 110 * 3 * 2
    assert full["usd"] > DOSSIER_NIGHTLY_BUDGET_USD
    nights = (full["usd"] / DOSSIER_NIGHTLY_BUDGET_USD).to_integral_value(rounding=ROUND_CEILING)
    assert nights > 3
    assert full["usd"] <= Decimal("0.25") * 3


def test_keys_stay_under_dossiers_and_reject_the_corpus():
    assert edition_markdown_key(EDITION, 1) == "dossiers/2026-10-18/1.md"
    assert edition_markdown_key(EDITION, 1, "1A") == "dossiers/2026-10-18/1/1A.md"
    assert edition_markdown_key(EDITION, "Technology-5") == "dossiers/2026-10-18/Technology-5.md"
    assert (
        edition_markdown_key(EDITION, "Technology-5", "Technology-5A")
        == "dossiers/2026-10-18/Technology-5/Technology-5A.md"
    )
    key = index_key("World", "Russia Ukraine War", "1A-Ukraine Oil Deal")
    assert key.startswith("dossiers/index/")
    r2_assert_dossier_key(key)
    for bad in ("live_corpus.db", "dossiers/../live_corpus.db", "public/data.json", "dossiers/public/1.md"):
        with pytest.raises(RuntimeError):
            assert_dossier_key(bad)


def test_put_private_object_does_not_replace_the_corpus():
    import urllib.parse

    from pipeline.r2 import R2Config, get_private_object, put_private_object

    paths = []

    class _Resp:
        def __init__(self, status, body=b""):
            self.status = status
            self.headers = {"Content-Length": str(len(body))}
            self._body = body

        def read(self, amount=-1):
            if amount is None or amount < 0:
                chunk, self._body = self._body, b""
                return chunk
            chunk, self._body = self._body[:amount], self._body[amount:]
            return chunk

        def close(self):
            return None

    def opener(request, timeout):
        del timeout
        path = urllib.parse.urlparse(request.full_url).path
        paths.append((request.get_method(), path))
        if request.get_method() == "PUT":
            assert request.data == b"briefing"
            return _Resp(200, b"")
        return _Resp(200, b"briefing")

    config = R2Config(
        access_key_id="AKIDEXAMPLE",
        endpoint="https://acct.r2.cloudflarestorage.com",
        secret_access_key="secret",
        bucket="perspectiverse",
    )
    assert put_private_object("dossiers/2026-10-18/1.md", b"briefing", config=config, opener=opener) == "uploaded"
    assert paths[0][0] == "PUT"
    assert paths[0][1].endswith("/dossiers/2026-10-18/1.md")
    assert "live_corpus.db" not in paths[0][1]
    assert get_private_object("dossiers/2026-10-18/1.md", config=config, opener=opener) == b"briefing"


def test_label_context_keeps_dossiers_off(monkeypatch):
    from pipeline import live

    settings = {
        "label_backend": "heuristic",
        "representative_posts": 6,
        "seed": 0,
        "openai_model": "m",
    }
    context = live._label_context(settings)
    assert context["dossiers"] is False
    assert context["dossier_store"] is None
    monkeypatch.setattr("pipeline.live.open_dossier_store", lambda: None)
    enabled = dict(settings, dossiers=True)
    context = live._label_context(enabled)
    assert context["dossiers"] is False


def _named_topic(name, topic_id, face_id, face_title, posts, post_count, face_count=None):
    topic = _topic(posts)
    topic["id"] = topic_id
    topic["name"] = name
    topic["post_count"] = post_count
    topic["summary"] = f"Old summary for {name}."
    face = topic["perspectives"][0]
    face["id"] = face_id
    face["title"] = face_title
    face["post_count"] = post_count if face_count is None else face_count
    face["summary"] = f"Old face summary for {face_title}."
    return topic


def _briefing_titles(prompts):
    titles = []
    for prompt in prompts:
        if not prompt.startswith("Write an internal briefing"):
            continue
        kind = "planet"
        title = ""
        for line in prompt.splitlines():
            if line.startswith("Kind: "):
                kind = line.split(": ", 1)[1]
            if line.startswith("Title: "):
                title = line.split(": ", 1)[1]
        titles.append((kind, title))
    return titles


def test_dossier_night_budget_is_the_min_of_allowance_and_cap_room():
    heavy = Decimal("0.978")
    assert dossier_night_budget(heavy) == Decimal("0")
    assert dossier_night_budget(heavy, reserve_usd=0) == Decimal("0.022")
    assert dossier_night_budget(Decimal("0.168")) == DOSSIER_NIGHTLY_BUDGET_USD
    assert dossier_night_budget(
        Decimal("0"), already_usd=Decimal("0.20"), nightly_usd=Decimal("0.25")
    ) == Decimal("0.05")
    assert dossier_night_budget(Decimal("0"), already_usd=Decimal("0.20")) == Decimal("0")
    assert DOSSIER_RUN_RESERVE_USD == Decimal("0.15")
    assert DOSSIER_NIGHTLY_BUDGET_USD == Decimal("0.09")


def test_budget_exhausted_still_publishes_and_keeps_summaries():
    from pipeline.spend_cap import SpendCapExceeded

    posts = _posts()
    topic = _named_topic("Big", 1, "1A", "Big view", posts, 100)
    before = topic["summary"]
    face_before = topic["perspectives"][0]["summary"]
    calls = []

    def generate(prompt):
        calls.append(prompt)
        raise SpendCapExceeded("daily stop", spent_usd=Decimal("1.00"))

    from pipeline import live

    context = {
        "dossiers": True,
        "dossier_store": MemoryDossierStore(),
        "summary_model": generate,
        "edition_date": EDITION,
        "dossier_budget": DossierBudget(spent_today=Decimal("0"), stop=Decimal("1")),
    }
    published = None
    try:
        live._apply_dossiers_if_enabled([topic], posts, context, reserve_usd=0)
        published = {"topics": [topic]}
    except SpendCapExceeded:
        published = None
    assert published is not None
    assert len(calls) == 1
    assert topic["summary"] == before
    assert topic["perspectives"][0]["summary"] == face_before
    assert "_dossier_action" not in topic

    capped = DossierBudget(spent_today=Decimal("0.978"), stop=Decimal("1"))
    quiet = []
    apply_dossiers_batch(
        [topic],
        posts,
        generate=_generate(quiet),
        store=MemoryDossierStore(),
        edition=EDITION,
        budget=capped,
        reserve_usd=DOSSIER_RUN_RESERVE_USD,
    )
    assert quiet == []
    assert topic["summary"] == before
    assert capped.spent == Decimal("0")


def test_deferred_rebuild_keeps_previous_dossier_and_carries_over():
    posts = _posts()
    big = _named_topic("Big", 1, "1A", "Big view", posts, 100)
    small = _named_topic("Small", 2, "2A", "Small view", posts, 5)
    previous = {
        "prompt_version": DOSSIER_PROMPT_VERSION,
        "summary": "Stored small summary stays while the rebuild waits.",
        "brief": "Stored small brief one. Stored small brief two. Stored small brief three.",
        "detail": (
            "Stored small paragraph one is long enough to stand.\n\n"
            "Stored small paragraph two is long enough to stand.\n\n"
            "Stored small paragraph three is long enough to stand."
        ),
        "post_uris": ["at://post/0"],
        "top_n": [{"uri": "at://post/0", "likes": 1}],
    }
    store = MemoryDossierStore()
    store.put_json(index_key("World", "Small"), previous)
    sampled = sample_posts(posts)
    big_cost = project_pair(
        sampled,
        kind="planet",
        title="Big",
        rivals=[],
        output_tokens=DOSSIER_OUTPUT_TOKENS_4PAGE,
    )["usd"]
    small_cost = project_pair(
        sampled,
        kind="planet",
        title="Small",
        rivals=[],
        output_tokens=DOSSIER_OUTPUT_TOKENS_4PAGE,
    )["usd"]
    planet_cost = max(big_cost, small_cost)
    prompts = []
    budget = DossierBudget(nightly_usd=planet_cost, spent_today=Decimal("0"), stop=Decimal("1"))
    apply_dossiers_batch(
        [small, big],
        posts,
        generate=_generate(prompts),
        store=store,
        edition=EDITION,
        budget=budget,
        reserve_usd=0,
    )
    assert _briefing_titles(prompts) == [("planet", "Big")]
    assert big["summary"] != "Old summary for Big."
    assert small["summary"] == previous["summary"]
    assert store.get_text(edition_markdown_key(EDITION, 2)) is None
    assert store.get_text(edition_markdown_key(EDITION, 1))

    prompts.clear()
    next_budget = DossierBudget(nightly_usd=planet_cost, spent_today=Decimal("0"), stop=Decimal("1"))
    apply_dossiers_batch(
        [small, big],
        posts,
        generate=_generate(prompts),
        store=store,
        edition=EDITION,
        budget=next_budget,
        reserve_usd=0,
    )
    assert _briefing_titles(prompts) == [("planet", "Small")]
    assert small["summary"] != previous["summary"]
    assert store.get_text(edition_markdown_key(EDITION, 2))
    assert ("planet", "Big") not in _briefing_titles(prompts)


def test_rebuild_order_is_biggest_planets_then_their_faces():
    posts = _posts()
    other_posts = _posts()
    for index, post in enumerate(other_posts):
        post["uri"] = f"at://other/{index}"
    big = _named_topic("Big", 1, "1A", "Small camp", posts, 80, face_count=10)
    big["perspectives"].append(
        {
            "id": "1B",
            "title": "Large camp",
            "summary": "Old large camp summary.",
            "brief": "Old large one. Old large two. Old large three.",
            "detail": (
                "Old large paragraph one is long enough to stand.\n\n"
                "Old large paragraph two is long enough to stand.\n\n"
                "Old large paragraph three is long enough to stand."
            ),
            "representative_posts": other_posts,
            "_face_member_uris": [post["uri"] for post in other_posts],
            "post_count": 70,
        }
    )
    mid = _named_topic("Mid", 2, "2A", "Mid view", posts, 40)
    small = _named_topic("Small", 3, "3A", "Small view", posts, 5)
    prompts = []
    apply_dossiers_batch(
        [small, mid, big],
        posts + other_posts,
        generate=_generate(prompts),
        store=MemoryDossierStore(),
        edition=EDITION,
        budget=DossierBudget(spent_today=Decimal("0"), stop=Decimal("1")),
        reserve_usd=0,
    )
    assert _briefing_titles(prompts) == [
        ("planet", "Big"),
        ("planet", "Mid"),
        ("planet", "Small"),
        ("perspective", "Large camp"),
        ("perspective", "Small camp"),
        ("perspective", "Mid view"),
        ("perspective", "Small view"),
    ]


def test_sample_command_prints_cost_and_does_not_call_the_model(tmp_path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise AssertionError("paid call")

    monkeypatch.setattr("pipeline.label._openai_generate", boom)
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"topics": [_topic()]}), encoding="utf-8")
    assert main(["sample", "--data", str(path), "--planets", "Russia Ukraine War"]) == 0
    printed = capsys.readouterr().out
    assert "No model was called" in printed
    assert "Dry run" in printed
    assert "Russia Ukraine War" in printed
    assert "$" in printed
    outline = main(["outline", "--data", str(path), "--planets", "Russia Ukraine War"])
    assert outline == 0
    text = capsys.readouterr().out
    assert "## Subject" in text
    assert "@user0.bsky.social" in text


def test_allowance_defaults_to_the_daily_target_and_is_configurable(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_DOSSIER_BUDGET_USD", raising=False)
    assert dossier_allowance_usd() == Decimal("0.09")
    fit = allowance_fit(DOSSIER_NIGHTLY_BUDGET_USD)
    assert fit["fits_target"] is True
    assert fit["total_usd"] == Decimal("0.25")
    old = allowance_fit(DOSSIER_ALLOWANCE_SUPERSEDED_USD)
    assert old["superseded_must_drop"] is True
    assert old["fits_fallback"] is False
    monkeypatch.setenv("PERSPECTIVERSE_DOSSIER_BUDGET_USD", "0.14")
    assert dossier_allowance_usd() == Decimal("0.14")
    assert allowance_fit(dossier_allowance_usd())["fits_fallback"] is True
    assert dossier_allowance_usd({"dossier_budget_usd": "0.05"}) == Decimal("0.05")


def test_filler_sentence_is_dropped_from_the_public_tiers():
    reader = enforce_no_repeat(
        summary="Oil Talks is the conversation these views share.",
        brief="Oil Talks is the conversation these views share. The posts name an oil deal.",
        detail="Oil Talks is the conversation these views share.\n\nShort.\n\nShort.",
        dossier=DOSSIER,
        forbidden=(),
        posts=_posts(),
        title="Oil Talks",
    )
    assert "conversation these views share" not in reader["summary"]
    assert "conversation these views share" not in reader["brief"]
    assert "conversation these views share" not in reader["detail"]
    _assert_tiers(reader["summary"], reader["brief"], reader["detail"])


def _edition_payload():
    def planet(section, topic_id, name, faces):
        return {
            "id": topic_id,
            "name": name,
            "category": section,
            "summary": f"{name} is the conversation these views share.",
            "brief": (
                f"{name} is the conversation these views share. "
                f"{faces[0][1]} says the first claim. "
                "A third sentence adds nothing new."
            ),
            "detail": (
                f"{name} is the conversation these views share.\n\n"
                "The second paragraph repeats the first claim in the same words as the brief.\n\n"
                "The third paragraph names a quote that is not in the posts above."
            ),
            "perspectives": [
                {
                    "id": face_id,
                    "title": title,
                    "summary": summary,
                    "brief": f"{summary} The brief adds a second sentence here. A third sentence stays.",
                    "detail": (
                        f"{summary}\n\n"
                        "A second paragraph adds a quote from the posts.\n\n"
                        "A third paragraph names the other view."
                    ),
                    "representative_posts": [
                        {
                            "uri": f"at://{topic_id}/{face_id}",
                            "author": "ada.bsky.social",
                            "text": summary,
                            "likes": 3,
                        }
                    ],
                }
                for face_id, title, summary in faces
            ],
        }

    world = planet("World", "World-1", "Oil Talks", [("World-1A", "Deal", "The oil deal enriches the negotiators.")])
    world["perspectives"].append(
        {
            "id": "World-1B",
            "title": "Aid",
            "summary": "The aid was steered aside.",
            "brief": "The aid was steered aside. A second sentence adds the harbor. A third names the vote.",
            "detail": "One.\n\nTwo is long enough to be its own paragraph here.\n\nThree is long enough as well.",
            "representative_posts": [
                {"uri": "at://world/b", "author": "bea.bsky.social", "text": "The harbor vote failed.", "likes": 2}
            ],
        }
    )
    politics = planet(
        "Politics",
        "Politics-1",
        "Vote",
        [("Politics-1A", "Early", "Early voting hours were cut.")],
    )
    return {
        "topics": [
            planet("World", 1, "Homepage Oil", [("1A", "Deal", "Homepage posts name the oil deal.")]),
        ],
        "sections": {"World": [world], "Politics": [politics]},
    }


def test_seeded_sample_is_stable_and_stratified():
    payload = _edition_payload()
    first = draw_summary_sample(payload, planets=3, seed=241)
    second = draw_summary_sample(payload, planets=3, seed=241)
    assert [row["item_id"] for row in first] == [row["item_id"] for row in second]
    sections = {row["section"] for row in first if row["kind"] == "planet"}
    assert sections == {"All topics", "Politics", "World"}
    multi = [row for row in first if row["planet_name"] == "Oil Talks" and row["kind"] == "perspective"]
    assert len(multi) == 1


def test_quality_report_counts_overlap_without_a_model():
    report = quality_report(_edition_payload())
    assert report["filler_items"] >= 1
    assert report["brief_overlap_items"] >= 1
    assert report["planets"] == 3


def test_replay_and_quality_commands_do_not_call_the_model(tmp_path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise AssertionError("paid call")

    monkeypatch.setattr("pipeline.label._openai_generate", boom)
    path = tmp_path / "data.json"
    payload = _edition_payload()
    path.write_text(json.dumps(payload), encoding="utf-8")
    sample = tmp_path / "sample.csv"
    assert main(["baseline", "--data", str(path), "--out", str(sample), "--planets", "2", "--seed", "241"]) == 0
    assert main(["quality", "--data", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "Before-state" in printed
    assert main(["replay", "--data", str(path), "--sample", str(sample)]) == 0
    replay = capsys.readouterr().out
    assert "Dry run" in replay
    assert "No model was called" in replay
    assert main(["smoke", "--data", str(path), "--seed", "241"]) == 0
    smoke = capsys.readouterr().out
    assert "Smoke test only" in smoke
    assert "Dry run" in smoke
