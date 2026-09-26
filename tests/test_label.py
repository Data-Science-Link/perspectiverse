import json

from pipeline.label import FALLBACK_TITLE, build_prompt, label_perspective, parse_label


def test_prompt_demands_json_only():
    prompt = build_prompt([{"text": "Rent is due.", "likes": 3}])
    assert '{"title"' in prompt
    assert "JSON only" in prompt


def test_parse_label_accepts_wrapped_json():
    parsed = parse_label('Sure thing {"title": "Rent Burden", "summary": "People cannot pay rent."}')
    assert parsed["title"] == "Rent Burden"


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


def test_auto_without_llm_uses_visible_fallback(monkeypatch):
    monkeypatch.setattr("pipeline.label.ollama_reachable", lambda timeout=0.4: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    labeled = label_perspective([{"text": "A post about housing.", "likes": 1}], ["housing"], backend="auto")
    assert labeled["title"] == FALLBACK_TITLE
    assert labeled["label_source"] == "fallback"
