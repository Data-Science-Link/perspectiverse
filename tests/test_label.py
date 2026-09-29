import json

from pipeline.label import FALLBACK_TITLE, build_prompt, label_perspective, label_topic, parse_label


def test_prompt_demands_json_only():
    prompt = build_prompt([{"text": "Rent is due.", "likes": 3}])
    assert '{"title"' in prompt
    assert "JSON only" in prompt
    assert "arguments" in prompt


def test_parse_label_accepts_wrapped_json():
    parsed = parse_label('Sure thing {"title": "Rent Burden", "summary": "People cannot pay rent."}')
    assert parsed["title"] == "Rent Burden"


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
