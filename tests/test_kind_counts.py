"""The three kind counts are a report. They do not change the edition."""

import json

from pipeline.edition_check import check_edition
from pipeline.kind_counts import measure_kind_counts, score_labeled_kinds


def _planet(name, texts, *, post_count=40, face_title=None, section="World"):
    return section, {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "category": section,
        "post_count": post_count,
        "summary": "A published planet.",
        "perspectives": [
            {
                "id": "0",
                "title": face_title or name,
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


def test_kind_counts_do_not_change_the_edition_or_the_duplicate_score():
    greet = _planet("Good Day", ["Good day everyone, hope you are well."], post_count=12)
    left = _planet("AI Control", ["People fear what ai will do to writing."], post_count=5, section="Technology")
    right = _planet("AI bots", ["The ai bots keep posting the same pitch."], post_count=5, section="Technology")
    big = _planet("AI Adoption", ["The ai adoption push is the same pitch."], post_count=40, section="Technology")
    other = _planet("Harbor Strike", ["Dock workers walked out at the harbor."], post_count=8, section="World")
    payload = _edition(greet, left, right, big, other)
    original = json.dumps(payload)
    counts = measure_kind_counts(payload)
    report = check_edition(payload, settings={"min_planet_posts": 30, "catalog_size": 10})
    assert json.dumps(payload) == original
    assert counts["changes_edition"] is False
    assert counts["greeting_titles"]["count"] == 1
    assert counts["greeting_titles"]["planets"][0]["name"] == "Good Day"
    assert counts["fragments"]["count"] == 1
    titles = {counts["fragments"]["pairs"][0]["left_title"], counts["fragments"]["pairs"][0]["right_title"]}
    assert titles == {"AI Control", "AI bots"}
    assert "duplicate_rate" in report
    assert report["duplicate_rate"]["before"]["planets"]["pairs"] > 0
    assert report["kind_counts"]["greeting_titles"]["count"] == 1


def test_fragment_count_stays_inside_one_section_and_under_20():
    same = _planet("School Surgeries", ["The school surgery rumor is the same claim."], post_count=19, section="Education")
    mate = _planet("School Medical Care", ["School medical care is the rumor again."], post_count=8, section="Education")
    elsewhere = _planet("School Lunch", ["School lunch is a different section."], post_count=6, section="Health")
    grown = _planet("School Board", ["The school board posted the same rumor."], post_count=20, section="Education")
    counts = measure_kind_counts(_edition(same, mate, elsewhere, grown))
    pairs = {(row["left_title"], row["right_title"]) for row in counts["fragments"]["pairs"]}
    assert pairs == {("School Medical Care", "School Surgeries")}


def test_stance_agreement_counts_same_subject_and_skips_disagreement():
    from pathlib import Path

    excerpt = json.loads(Path("tests/fixtures/stance_issue_excerpts.json").read_text())["256"]
    same = _planet("Israel", ["Israel is condemned in these posts."], post_count=40)
    same[1]["perspectives"] = excerpt["perspectives"]
    opposed = _planet("Israel Policy", ["A placeholder."], post_count=40)
    opposed[1]["perspectives"] = [
        {
            "id": "a",
            "title": "Israel Policy",
            "summary": "Posts about Israel policy",
            "post_count": 20,
            "representative_posts": [
                {"text": "Israel is a genocidal terrorist state."},
                {"text": "These killings are horrific and wrong."},
            ],
        },
        {
            "id": "b",
            "title": "Israel Policy 2",
            "summary": "Posts about Israel policy",
            "post_count": 20,
            "representative_posts": [
                {"text": "I support and defend Israel. The operation was successful."},
                {"text": "Israel deserves support. The strikes were effective."},
            ],
        },
    ]
    agreed = measure_kind_counts(_edition(same))
    split = measure_kind_counts(_edition(opposed))
    assert agreed["stance_agreement"]["count"] == 1
    assert split["stance_agreement"]["count"] == 0


def test_labeled_recall_is_raw_counts_and_false_flags():
    greet = _planet("Happy Sunday", ["Happy Sunday, have a good one."], post_count=6)
    other = _planet("Good Morning", ["Good morning friends."], post_count=8)
    news = _planet("Oil Prices", ["Brent crude rose after the supply cut."], post_count=40)
    left = _planet("AI Control", ["People fear what ai will do."], post_count=5, section="Technology")
    right = _planet("AI bots", ["Those ai bots posted again."], post_count=5, section="Technology")
    payload = _edition(greet, other, news, left, right)
    planets = [
        {"pair_id": "p1", "level": "planet", "section": "Other", "title_a": "Happy Sunday", "title_b": "Good Morning", "is_duplicate": "yes"},
        {"pair_id": "p2", "level": "planet", "section": "Technology", "title_a": "AI Control", "title_b": "AI bots", "is_duplicate": "yes"},
        {"pair_id": "p3", "level": "planet", "section": "World", "title_a": "Oil Prices", "title_b": "Good Morning", "is_duplicate": "no"},
        {"pair_id": "p4", "level": "planet_leak", "section": "Other", "title_a": "Happy Sunday", "title_b": "Good Morning", "is_duplicate": "yes"},
        {"pair_id": "p5", "level": "planet", "section": "Other", "title_a": "Happy Sunday", "title_b": "Good Morning", "is_duplicate": "unsure"},
    ]
    faces = [
        {"pair_id": "c1", "level": "face_census", "planet": "Israel", "title_a": "Israel Condemned", "title_b": "Israel Influence", "is_duplicate": "yes"},
        {"pair_id": "c2", "level": "face_census", "planet": "Israel", "title_a": "Left", "title_b": "Right", "is_duplicate": "no"},
    ]
    host = _planet("Israel", ["Israel is condemned in these posts."], post_count=40)
    excerpt = json.loads(open("tests/fixtures/stance_issue_excerpts.json").read())["256"]
    host[1]["perspectives"] = excerpt["perspectives"]
    payload["sections"]["World"].append(host[1])
    scored = score_labeled_kinds(payload, planets, faces)
    greeting = scored["labeled"]["greeting_titles"]
    fragments = scored["labeled"]["fragments"]
    stance = scored["labeled"]["stance_agreement"]
    assert greeting["recall"] == "1 of 1"
    assert greeting["false_flags"] == 0
    assert greeting["no"] == 1
    assert fragments["recall"] == "1 of 1"
    assert fragments["false_flags"] == 0
    assert stance["recall"] == "1 of 1"
    assert stance["false_flags"] == 0
    assert stance["no"] == 1
