import json

from pipeline.label import (
    FALLBACK_TITLE,
    build_prompt,
    label_perspective,
    label_topic,
    parse_label,
    resolve_openai_base_url,
    resolve_openai_model,
    _openai_generate,
)


def test_prompt_demands_json_only():
    prompt = build_prompt([{"text": "Rent is due.", "likes": 3}])
    assert '{"title"' in prompt
    assert "JSON only" in prompt
    assert "arguments" in prompt
    assert "paraphrase" in prompt
    assert "Anti Republican" in prompt
    assert "insult" in prompt.lower()


def test_weak_term_does_not_become_the_face_title():
    posts = [
        {"text": "AI evangelists are morally unequipped to oversee this technology.", "likes": 9},
        {"text": "Those AI evangelists keep shipping it without consent.", "likes": 4},
    ]
    calls = {"n": 0}

    def generate(prompt):
        calls["n"] += 1
        if "not publishable" in prompt:
            return json.dumps(
                {
                    "title": "Unfit Evangelists",
                    "summary": "The posts say AI evangelists are morally unequipped to govern the technology.",
                    "arguments": [
                        "AI evangelists are morally unequipped to oversee this technology.",
                        "Those AI evangelists keep shipping it without consent.",
                    ],
                }
            )
        return json.dumps(
            {
                "title": "AI Criticism",
                "summary": "These posts share various concerns about the tools.",
                "arguments": [
                    "AI evangelists are morally unequipped to oversee this technology.",
                    "Those AI evangelists keep shipping it without consent.",
                ],
            }
        )

    labeled = label_perspective(posts, ["most"], generate=generate)
    assert calls["n"] >= 2
    assert labeled["title"] not in {"Most", "AI Criticism", "Mixed remarks"}
    assert "evangelist" in labeled["title"].lower()
    assert "various concerns" not in labeled["summary"].lower()
    assert "evangelists" in labeled["summary"].lower()


def test_faces_that_share_no_subject_word_are_different_stories():
    from pipeline.label import faces_share_vocabulary

    judicial = {
        "title": "Judicial Compliance",
        "summary": "Judges' orders are being ignored.",
        "representative_posts": [
            {"text": "Nothing happens when officials defy a judge's order and skip the hearing."}
        ],
    }
    powell = {
        "title": "No Prosecution",
        "summary": "The department will not charge the former chair.",
        "representative_posts": [
            {"text": "The Justice Department will not reopen the Powell renovation investigation."}
        ],
    }
    death = {
        "title": "Death Penalty",
        "summary": "The execution of Christa Pike was torture.",
        "representative_posts": [{"text": "Christa Pike survived a botched execution in Tennessee."}],
    }
    needle = {
        "title": "Lethal Injection",
        "summary": "Lethal injection made Christa Pike suffer.",
        "representative_posts": [{"text": "Christa Pike suffered during the botched execution."}],
    }
    assert faces_share_vocabulary([judicial, powell]) is False
    assert faces_share_vocabulary([death, needle]) is True


def test_different_stories_are_not_one_subject():
    from pipeline.label import perspectives_share_subject

    faces = [
        {"title": "Pentagon Religion", "summary": "The defense secretary opened a religious affairs office."},
        {"title": "Church Alliance", "summary": "A church is partnering with artists on outreach."},
    ]
    assert perspectives_share_subject(faces, backend="heuristic") is True
    assert (
        perspectives_share_subject(
            faces,
            backend="openai",
            generate=lambda _prompt: '{"same": false}',
        )
        is False
    )
    assert (
        perspectives_share_subject(
            faces,
            backend="openai",
            generate=lambda _prompt: "not json",
        )
        is True
    )


def test_camp_title_is_replaced_with_the_claim_terms():
    posts = [{"text": "The rent increase on my block is the whole story tonight.", "likes": 4}]
    labeled = label_perspective(
        posts,
        ["rent", "increase"],
        generate=lambda _prompt: json.dumps(
            {
                "title": "Anti Landlord",
                "summary": "The rent increase on the block is the story.",
                "arguments": [
                    "The rent increase on the block is the whole story.",
                    "The rent increase tonight is what the block is talking about.",
                ],
            }
        ),
    )
    assert labeled["title"] == "Rent Increase"
    assert "Astra" not in labeled["summary"]


def test_invented_entity_is_dropped_and_a_paraphrase_is_kept():
    posts = [{"text": "The rent increase on my block is the whole story tonight.", "likes": 4}]
    labeled = label_perspective(
        posts,
        ["rent"],
        generate=lambda _prompt: json.dumps(
            {
                "title": "Rent Burden",
                "summary": "People are talking about the rent increase.",
                "arguments": [
                    "The rent increase on the block is the whole story.",
                    "OpenAI cancelled GPT-6.1 Astra yesterday.",
                ],
            }
        ),
    )
    arguments = labeled.get("arguments") or []
    assert arguments
    assert all("Astra" not in item and "OpenAI" not in item and "6.1" not in item for item in arguments)
    assert "rent increase" in arguments[0]


def test_duplicate_titles_get_a_suffix():
    from pipeline.label import unique_label

    seen: set[str] = set()
    assert unique_label("Anti Trump", seen) == "Anti Trump"
    assert unique_label("Anti Trump", seen) == "Anti Trump 2"


def test_titles_alike_catches_a_numbered_copy_and_not_a_different_claim():
    from pipeline.label import titles_alike

    assert titles_alike("Pro Ukraine", "Pro Ukraine 2")
    assert titles_alike("AI Criticism", "AI Critique")
    assert not titles_alike("Pro Ukraine", "Oil Crisis")


def test_heuristic_summary_uses_a_shown_sentence():
    from pipeline.label import heuristic_label

    labeled = heuristic_label(
        ["rent"],
        [{"text": "Half my paycheck is rent and the lease still went up.", "likes": 4}],
    )
    assert "paycheck" in labeled["summary"]
    assert "concentrate on" not in labeled["summary"]


def test_parse_label_accepts_wrapped_json():
    parsed = parse_label('Sure thing {"title": "Rent Burden", "summary": "People cannot pay rent."}')
    assert parsed["title"] == "Rent Burden"


def test_parse_label_accepts_unescaped_quotes_inside_strings():
    raw = (
        '{"title": "AI Terminology", "summary": "Prefer the term "machine learning" over "AI" here", '
        '"arguments": ["Using "AI" chases funding.", "The narrower name is more accurate."]}'
    )
    parsed = parse_label(raw)
    assert parsed is not None
    assert parsed["title"] == "AI Terminology"
    assert "machine learning" in parsed["summary"]
    assert parsed["arguments"][0].startswith("Using")


def test_parse_label_keeps_arguments_and_topic_name():
    parsed = parse_label(
        '{"name": "AI Jobs", "title": "AI Jobs", "summary": "People argue about automation.", '
        '"arguments": ["Payroll is already changing.", "The threat is quiet."]}'
    )
    assert parsed["name"] == "AI Jobs"
    assert parsed["arguments"][0].startswith("Payroll")


def test_label_topic_without_llm_is_heuristic(monkeypatch):
    monkeypatch.setattr("pipeline.label.ollama_reachable", lambda timeout=0.4: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    labeled = label_topic(
        [{"text": "The model release is eating junior writing jobs this quarter.", "likes": 12}],
        ["model", "jobs"],
        backend="auto",
    )
    assert labeled["name"] == "Model Jobs"
    assert labeled["label_source"] == "heuristic"


def test_invalid_model_output_retries_then_falls_back():
    calls = {"n": 0}

    def generate(_prompt):
        calls["n"] += 1
        return "not json at all"

    labeled = label_perspective(
        [{"text": "Rent is due again.", "likes": 2}],
        ["rent", "housing"],
        generate=generate,
    )
    assert calls["n"] == 2
    assert labeled["title"] == FALLBACK_TITLE
    assert "rent" in labeled["summary"]


def test_second_try_can_succeed():
    calls = {"n": 0}

    def generate(_prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return "nope"
        return json.dumps({"title": "Wage Floor", "summary": "People want a higher wage."})

    labeled = label_perspective([{"text": "Raise the wage.", "likes": 8}], ["wage"], generate=generate)
    assert calls["n"] == 2
    assert labeled["title"] == "Wage Floor"
    assert labeled["label_source"] == "model"


def test_auto_without_llm_uses_heuristic_names(monkeypatch):
    monkeypatch.setattr("pipeline.label.ollama_reachable", lambda timeout=0.4: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    labeled = label_perspective(
        [{"text": "A longer post about housing costs this week in the city.", "likes": 1}],
        ["housing"],
        backend="auto",
    )
    assert labeled["title"] == "Housing"
    assert labeled["label_source"] == "heuristic"
    assert len(labeled["arguments"]) >= 2


def test_empty_openai_base_url_defaults_to_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert resolve_openai_base_url() == "https://api.openai.com/v1"
    assert resolve_openai_model() == "gpt-4o-mini"


def test_deepinfra_base_url_picks_llama_default(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepinfra.com/v1/openai")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert resolve_openai_model() == "meta-llama/Llama-3.3-70B-Instruct-Turbo"


def test_mocked_openai_generate_posts_to_deepinfra(monkeypatch):
    seen = {}

    def fake_read_json(url, *, timeout, data=None, headers=None):
        seen["url"] = url
        seen["authorization"] = (headers or {}).get("Authorization", "")
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"title": "Rent Burden", "summary": "People cannot pay rent."}
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepinfra.com/v1/openai")
    monkeypatch.setenv("OPENAI_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    raw = _openai_generate("hello", resolve_openai_model())
    assert "Rent Burden" in raw
    assert seen["url"] == "https://api.deepinfra.com/v1/openai/chat/completions"
    assert seen["authorization"] == "Bearer test-not-a-real-key"
    from pipeline.http_json import _allowed

    assert _allowed(seen["url"])

