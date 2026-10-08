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
    monkeypatch.setattr(script, "_load_planets", boom)
    monkeypatch.setattr(script, "run_shadow", boom)
    monkeypatch.setattr(script, "run_planet_shadow", boom)
    assert script.main(["--posts", "1000", "--max-spend", "1"]) == 2
    assert script.main(["--planets", "planets.json", "--max-spend", "1"]) == 2


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
    assert report["claims_lost"] == Decimal("0.25")
    assert report["claim_pass"] is False
    assert report["lost_pass"] is False
    assert "section_agreement" not in report
    passing = script.agreement_report([claim] * 20, [same] * 20)
    assert passing["claim_pass"] is True
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
            {"is_claim": True, "spam_score": 0.05, "section": None, "claim_score": 0.8} for _post in posts
        ]
        return decisions, script.batch_call_token_estimate(len(posts))

    posts = [{"uri": f"at://{index}", "clean_text": "Congress should publish the rules today now"} for index in range(40)]
    report = script.run_shadow(posts, cap=Decimal("0.001"), per_post_call=per_post, batch_call=batch)
    assert 0 < report["posts_both_ways"] < 40
    assert report["posts_both_ways"] <= calls["per"]
    assert calls["batch"] >= 1
    assert report["stopped_early"] is True
    assert report["spent_usd"] <= Decimal("0.001")
    assert report["claim_pass"] is True


def test_planet_section_matches_the_per_post_majority():
    script = _script()
    assert script.majority_sections(["World", "Politics", "Politics"]) == ["Politics"]
    assert script.majority_sections(["World", "Politics"]) == ["Politics", "World"]
    planets = [
        {
            "name": f"planet-{index}",
            "summary": "States should publish the mail ballot rules.",
            "arguments": ["Voters need the rules before November."],
            "sections": ["Politics", "Politics", "World"],
        }
        for index in range(10)
    ]

    def agree(_planet, _spent, _cap):
        return "Politics", 490

    report = script.run_planet_shadow(planets, cap=Decimal("0.03"), planet_call=agree)
    assert report["planets_compared"] == 10
    assert report["agreement"] == Decimal("1")
    assert report["agreement_pass"] is True
    assert report["disagreements"] == []

    def mostly(_planet, _spent, _cap):
        mostly.n += 1
        return ("Sports" if mostly.n > 9 else "Politics"), 490

    mostly.n = 0
    tight = script.run_planet_shadow(planets, cap=Decimal("0.03"), planet_call=mostly)
    assert tight["agreement"] == Decimal("0.9")
    assert tight["agreement_pass"] is True
    assert len(tight["disagreements"]) == 1

    def miss_two(_planet, _spent, _cap):
        miss_two.n += 1
        return ("Sports" if miss_two.n > 8 else "Politics"), 490

    miss_two.n = 0
    missed = script.run_planet_shadow(planets, cap=Decimal("0.03"), planet_call=miss_two)
    assert missed["agreement"] == Decimal("0.8")
    assert missed["agreement_pass"] is False


def test_planet_mode_stops_when_the_shared_cap_is_spent():
    script = _script()

    def boom(*_args, **_kwargs):
        raise AssertionError("a planet call must not start once the cap is spent")

    planets = [
        {
            "name": "mail",
            "summary": "States should publish the rules.",
            "arguments": "Voters need them.",
            "sections": ["Politics"],
        }
    ]
    report = script.run_planet_shadow(
        planets,
        spent=Decimal("0.03"),
        cap=Decimal("1"),
        planet_call=boom,
    )
    assert report["calls"] == 0
    assert report["planets_compared"] == 0
    assert report["stopped_early"] is True
    assert report["cap_usd"] == Decimal("0.03")
    assert report["spent_usd"] == Decimal("0.03")
