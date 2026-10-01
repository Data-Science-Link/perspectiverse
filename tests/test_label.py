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

