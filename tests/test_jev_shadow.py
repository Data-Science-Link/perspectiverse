"""Shadow-test budget and agreement math. No TypeSafe calls."""

import importlib.util
from decimal import Decimal
from pathlib import Path

from pipeline.costs import jev_cost_usd


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "jev_shadow_test.py"
    spec = importlib.util.spec_from_file_location("jev_shadow_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_shadow_refuses_to_run_without_a_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    script = _script()

    def boom(*_args, **_kwargs):
        raise AssertionError("the shadow test must not call TypeSafe without a key")

    monkeypatch.setattr(script, "_load_posts", boom)
    monkeypatch.setattr(script, "run_shadow", boom)
    assert script.main(["--posts", "1000", "--max-spend", "1"]) == 2


def test_spend_cap_is_three_cents():
    script = _script()
    assert script.MAX_SPEND_USD == Decimal("0.03")
    assert script.clamp_spend_cap(Decimal("1")) == Decimal("0.03")
    assert script.clamp_spend_cap(Decimal("0.01")) == Decimal("0.01")
    assert script.call_would_exceed(Decimal("0.02998"), 600)
    assert not script.call_would_exceed(Decimal("0"), 600)


def test_agreement_bars():
    script = _script()
    claim = {"is_claim": True, "spam_score": 0.1, "section": "World", "claim_score": 0.9}
    missed = {"is_claim": False, "spam_score": None, "section": "", "claim_score": 0.2}
    same = {"is_claim": True, "spam_score": None, "section": "World", "claim_score": 0.88}
    other = {"is_claim": True, "spam_score": None, "section": "Sports", "claim_score": 0.7}
    report = script.agreement_report([claim, claim, claim, claim], [same, same, other, missed])
    assert report["compared"] == 4
    assert report["claim_agreement"] == Decimal("0.75")
    assert report["section_agreement"] == Decimal("0.5")
    assert report["claims_lost"] == Decimal("0.25")
    assert report["claim_pass"] is False
    assert report["section_pass"] is False
    assert report["lost_pass"] is False
    passing = script.agreement_report([claim] * 20, [same] * 20)
    assert passing["claim_pass"] is True
    assert passing["section_pass"] is True
    assert passing["lost_pass"] is True


def test_run_shadow_stops_at_the_cap_without_network():
    script = _script()
    calls = {"per": 0, "batch": 0}

    def per_post(_post):
        calls["per"] += 1
        decision = {"is_claim": True, "spam_score": 0.05, "section": "Politics", "claim_score": 0.8}
        return decision, 600

    def batch(posts, _spent, _cap):
        calls["batch"] += 1
        decisions = [
            {"is_claim": True, "spam_score": None, "section": "Politics", "claim_score": 0.8} for _post in posts
        ]
        return decisions, 2_000

    posts = [{"uri": f"at://{index}", "clean_text": "Congress should publish the rules today now"} for index in range(40)]
    report = script.run_shadow(posts, cap=Decimal("0.001"), per_post_call=per_post, batch_call=batch)
    assert 0 < report["posts_both_ways"] < 40
    assert report["posts_both_ways"] <= calls["per"]
    assert calls["batch"] >= 1
    assert report["stopped_early"] is True
    assert report["spent_usd"] <= Decimal("0.001")
    assert report["claim_pass"] is True
