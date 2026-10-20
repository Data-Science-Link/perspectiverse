"""Kind counts use their own signals, tune on seed 273, and stay report-only."""

import ast
import json
from pathlib import Path

from pipeline.edition_check import check_edition
from pipeline.kind_counts import (
    WEEKLY_BLIND_SAMPLE_ENABLED,
    blind_label_cost,
    cross_post_agreement,
    draw_weekly_sample,
    fragment_pairs,
    greeting_planets,
    measure_kind_counts,
    score_labeled_kinds,
    surface_entities,
    within_post_agreement,
)


def _planet(name, texts, *, post_count=40, section="World", faces=None):
    return section, {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "category": section,
        "post_count": post_count,
        "summary": "A published planet.",
        "perspectives": faces
        or [
            {
                "id": "0",
                "title": name,
                "summary": "One face.",
                "post_count": post_count,
                "representative_posts": [{"text": text, "likes": 1} for text in texts],
            }
        ],
    }


def _edition(*scoped):
    sections: dict[str, list] = {}
    for section, planet in scoped:
        sections.setdefault(section, []).append(planet)
    return {"last_updated": "2026-10-19", "topics": [], "sections": sections}


def _face(title, texts):
    return {
        "id": title.lower().replace(" ", "-"),
        "title": title,
        "summary": title,
        "post_count": len(texts),
        "representative_posts": [{"text": text} for text in texts],
    }


def test_kind_count_module_does_not_import_the_fixes():
    tree = ast.parse(Path("pipeline/kind_counts.py").read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    banned = {"pipeline.story_attach", "pipeline.stance", "pipeline.chitchat_guard", "pipeline.perspectives", "pipeline.label_kinds"}
    assert banned.isdisjoint(modules)
    source = Path("pipeline/kind_counts.py").read_text(encoding="utf-8")
    assert "local_faces_fold" not in source
    assert "BIG_PLANET" not in source
    assert "specific_stems" not in source


def test_signals_are_entities_and_per_post_agreement_not_the_old_rules():
    assert surface_entities("AI Control") == {"ai"}
    assert surface_entities("School Surgeries") == set()
    short = ["Morning friends hope sunday stays easy."] * 3
    news = [
        "Brent crude rose after the refinery fire in Houston.",
        "The senate debated a different harbor bill tonight.",
    ]
    assert (within_post_agreement(short) or 0) > (within_post_agreement(news) or 0)
    same = ["Alpha market rally continues through the close."] * 2
    mixed_left = ["Alpha market rally continues through the close.", "Zebra quilt patterns differ."]
    mixed_right = ["Alpha market rally continues through the close.", "Quilt patterns differ widely today."]
    pairwise = cross_post_agreement(mixed_left, mixed_right)
    from pipeline.cluster_math import vectorize
    import numpy as np

    matrix = vectorize(mixed_left + mixed_right)
    left_mean = matrix[:2].mean(axis=0)
    right_mean = matrix[2:].mean(axis=0)
    left_mean = left_mean / np.linalg.norm(left_mean)
    right_mean = right_mean / np.linalg.norm(right_mean)
    centroid = float(np.dot(left_mean, right_mean))
    assert pairwise is not None
    assert abs(pairwise - centroid) > 1e-6
    assert cross_post_agreement(same, same) > 0.9


def test_counts_do_not_change_the_edition_and_the_duplicate_score_stays():
    greet = _planet(
        "Easy Sunday",
        ["Morning friends hope sunday stays easy.", "Sunday stays easy for friends this morning."],
        post_count=6,
        section="Other",
    )
    named = _planet(
        "Good Day",
        ["Brent crude rose after the refinery fire in Houston and the harbor closed."],
        post_count=40,
    )
    left = _planet("AI Control", ["People discuss control of software."], post_count=5, section="Technology")
    right = _planet("AI bots", ["Bots posted again overnight."], post_count=5, section="Technology")
    school = _planet("School Surgeries", ["The school rumor spread."], post_count=8, section="Education")
    mate = _planet("School Medical Care", ["Medical care rumors returned."], post_count=8, section="Education")
    payload = _edition(greet, named, left, right, school, mate)
    original = json.dumps(payload)
    greetings = greeting_planets(
        payload,
        {"min_sparse": 1.1, "min_agreement": 0.5, "max_median_words": 12},
    )
    fragments = fragment_pairs(payload, {"min_shared_entities": 1, "max_posts": 12})
    report = check_edition(payload, settings={"min_planet_posts": 30, "catalog_size": 10})
    assert json.dumps(payload) == original
    assert [row["name"] for row in greetings] == ["Easy Sunday"]
    assert "Good Day" not in {row["name"] for row in greetings}
    titles = {(row["left_title"], row["right_title"]) for row in fragments}
    assert ("AI Control", "AI bots") in titles or ("AI bots", "AI Control") in titles
    assert not any("School" in row["left_title"] for row in fragments)
    assert report["duplicate_rate"]["before"]["planets"]["pairs"] > 0
    assert report["kind_counts"]["weekly_blind_sample"]["enabled"] is False
    assert report["kind_counts"]["changes_edition"] is False


def test_held_out_recall_uses_seed_273_and_skips_the_tune_rows():
    def short(name, section="Other"):
        return _planet(
            name,
            ["Morning friends hope sunday stays easy.", "Sunday stays easy for friends this morning."],
            post_count=6,
            section=section,
        )

    def news(name):
        return _planet(
            name,
            [
                "Brent crude rose after the refinery fire in Houston.",
                "Senators debated a harbor bill with different cargo rules.",
            ],
            post_count=40,
        )

    planets = [
        short("Easy One"),
        short("Easy Two"),
        short("Easy Three"),
        news("Oil Desk"),
        news("Harbor Desk"),
        news("Senate Desk"),
    ]
    payload = _edition(*planets)
    rows = [
        {"pair_id": "g1", "level": "planet", "section": "Other", "title_a": "Easy One", "title_b": "Easy Two", "is_duplicate": "yes", "band": "B0"},
        {"pair_id": "g2", "level": "planet", "section": "Other", "title_a": "Easy One", "title_b": "Easy Three", "is_duplicate": "yes", "band": "B0"},
        {"pair_id": "g3", "level": "planet", "section": "Other", "title_a": "Easy Two", "title_b": "Easy Three", "is_duplicate": "yes", "band": "B0"},
        {"pair_id": "n1", "level": "planet", "section": "World", "title_a": "Oil Desk", "title_b": "Harbor Desk", "is_duplicate": "no", "band": "B0"},
        {"pair_id": "n2", "level": "planet", "section": "World", "title_a": "Oil Desk", "title_b": "Senate Desk", "is_duplicate": "no", "band": "B0"},
        {"pair_id": "n3", "level": "planet", "section": "World", "title_a": "Harbor Desk", "title_b": "Senate Desk", "is_duplicate": "no", "band": "B0"},
        {"pair_id": "s1", "level": "planet", "section": "Technology", "title_a": "AI One", "title_b": "AI Two", "is_duplicate": "yes", "band": "B1"},
    ]
    payload["sections"]["Technology"] = [
        _planet("AI One", ["Models changed."], post_count=4, section="Technology")[1],
        _planet("AI Two", ["Bots changed."], post_count=4, section="Technology")[1],
    ]
    scored = score_labeled_kinds(
        payload,
        rows,
        [],
        greeting_ids={"g1", "g2", "g3"},
        planet_spot_ids=set(),
        face_spot_ids=set(),
        bands={},
    )
    greeting = scored["labeled"]["greeting_titles"]
    assert greeting["seed"] == 273
    assert greeting["tuned_on"] > 0
    assert greeting["holdout"] > 0
    assert greeting["yes"] < 3
    assert " of " in greeting["recall"]
    fragment = scored["labeled"]["fragments"]
    assert fragment["flagged_yes"] <= fragment["yes"]
    assert scored["weekly_blind_sample"]["enabled"] is False


def test_weekly_sample_is_off_and_the_cost_fits_the_daily_budget():
    assert WEEKLY_BLIND_SAMPLE_ENABLED is False
    cost = blind_label_cost()
    assert cost["paid_calls"] == 0
    assert cost["planet_pairs"] == 20
    assert cost["face_pairs"] == 10
    assert float(cost["usd_per_week"]) > 0
    assert float(cost["usd_per_day"]) * 7 < 0.25
    assert float(cost["usd_per_week"]) < 0.01
    left = _planet("Alpha", ["Alpha cargo moved."], post_count=5)
    right = _planet("Beta", ["Beta cargo moved."], post_count=5)
    host = _planet(
        "Show",
        ["placeholder"],
        faces=[_face("Left View", ["The show was fine."]), _face("Right View", ["The show was fine too."])],
    )
    drawn = draw_weekly_sample(_edition(left, right, host), seed=27343)
    assert 1 <= len(drawn["planet_pairs"]) <= 20
    assert len(drawn["face_pairs"]) == 1
    assert "cosine" not in drawn["planet_pairs"][0]
    assert "band" not in drawn["face_pairs"][0]
    counts = measure_kind_counts(_edition(left, right))
    assert counts["weekly_blind_sample"]["planet_pairs"] == []
