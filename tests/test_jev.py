import json

from pipeline.jev import apply_jev, describe_jev, reset_jev_state


def _post(uri: str, text: str) -> dict:
    return {
        "uri": uri,
        "author": "ada",
        "text": text,
        "clean_text": text,
        "likes": 1,
        "created_at": "2026-09-28T00:00:00Z",
    }


def _answer(spam: float, section: str = "World", claim: float | None = None) -> dict:
    answers = {
        "spam": {"type": "noul", "noul": spam},
        "section": {
            "type": "choice",
            "choice": section,
            "confidence": 0.74,
            "probabilities": {section: 0.74, "Other": 0.26},
        },
    }
    if claim is not None:
        answers["claim"] = {"type": "noul", "noul": claim}
    return {"model": "jev-1.13.0", "answers": answers}


def test_missing_key_keeps_posts(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    reset_jev_state()
    posts = [_post("at://a", "buy followers and a crypto giveaway tonight please")]
    assert apply_jev(posts) == posts
    assert "unset" in describe_jev()


def test_spam_drop_and_section_assignment(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_jev_state()

    def fake(url, **kwargs):
        state = json.loads(kwargs["data"].decode("utf-8"))["state"]
        if "giveaway" in state:
            return _answer(0.91, "Other")
        return _answer(0.12, "Education")

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    labeled = _post("at://keep", "Already labeled housing post with enough words here.")
    labeled["section"] = "Business"
    labeled["section_confidence"] = 0.5
    kept = apply_jev(
        [
            _post("at://spam", "Join my crypto giveaway and follow back right now please"),
            _post("at://real", "The school board closed another classroom and the teachers walked out."),
            labeled,
        ]
    )
    uris = [post["uri"] for post in kept]
    assert uris == ["at://real", "at://keep"]
    real = kept[0]
    assert real["section"] == "Education"
    assert real["spam_score"] == 0.12
    assert kept[1]["section"] == "Business"


def test_transport_failure_keeps_the_post(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_jev_state()

    def boom(url, **kwargs):
        raise RuntimeError("Request failed for api.typesafe.ai: timed out")

    monkeypatch.setattr("pipeline.jev.read_json", boom)
    posts = [_post("at://a", "A civic argument about rent that should survive a Jev outage today.")]
    assert apply_jev(posts) == posts


def test_overloaded_response_is_retried(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_jev_state()
    calls = {"n": 0}

    def flaky(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("HTTP 529 from api.typesafe.ai")
        return _answer(0.2, "World")

    monkeypatch.setattr("pipeline.jev.read_json", flaky)
    monkeypatch.setattr("pipeline.jev.time.sleep", lambda _delay: None)
    kept = apply_jev([_post("at://a", "Diplomats met again after the latest cease fire proposal today.")])
    assert calls["n"] == 2
    assert kept[0]["section"] == "World"


def test_claim_question_flags_fandom_without_dropping_it(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_jev_state()
    seen = {}

    def fake(url, **kwargs):
        body = json.loads(kwargs["data"].decode("utf-8"))
        seen["questions"] = set(body["questions"])
        state = body["state"].lower()
        if "phillies" in state:
            return _answer(0.1, "Sports", claim=0.08)
        return _answer(0.1, "Politics", claim=0.91)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    kept = apply_jev(
        [
            _post("at://fandom", "The Phillies bullpen was worthless again and I cannot watch."),
            _post("at://claim", "Congress should publish the mail ballot rules before November."),
        ]
    )
    assert "claim" in seen["questions"]
    by_uri = {post["uri"]: post for post in kept}
    assert by_uri["at://fandom"]["is_claim"] is False
    assert by_uri["at://claim"]["is_claim"] is True


def test_rejected_key_disables_later_calls(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    reset_jev_state()

    def rejected(url, **kwargs):
        raise RuntimeError("HTTP 401 from api.typesafe.ai")

    monkeypatch.setattr("pipeline.jev.read_json_value", rejected)
    assert "HTTP 401" in describe_jev()
    posts = [_post("at://a", "A remark that must not be dropped when the key is rejected.")]
    assert apply_jev(posts) == posts
