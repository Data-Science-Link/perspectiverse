"""Free edition self-check. No network."""

import json

from pipeline.edition_check import (
    check_edition,
    check_faces_different,
    check_junk,
    check_label,
    check_post_floor,
    check_title_fit,
    render_markdown,
    thin_sections,
    title_fits,
)

SETTINGS = {"min_planet_posts": 30, "catalog_size": 10}


def _planet(**overrides):
    planet = {
        "id": "World-1",
        "name": "Ukraine Sanctions",
        "category": "World",
        "summary": "Posts argue about sanctions on Russia over the war in Ukraine.",
        "post_count": 40,
        "perspectives": [
            {
                "title": "Sanctions Hurt Russia",
                "summary": "The posts say sanctions are costing Russia.",
                "top_terms": ["sanctions", "russia", "ukraine"],
                "post_count": 40,
                "representative_posts": [
                    {"text": "Sanctions on Russia are the right response to the Ukraine war.", "likes": 3},
                    {"text": "Ukraine needs those Russia sanctions to hold.", "likes": 2},
                ],
            }
        ],
    }
    planet.update(overrides)
    return planet


def test_title_fits_when_words_are_in_the_posts():
    ok, _detail = title_fits(
        "Ukraine Sanctions",
        "Sanctions on Russia are the right response to the Ukraine war.",
    )
    assert ok


def test_title_fails_when_the_words_are_absent():
    ok, detail = title_fits("Toilet Paper", "The election turnout looks high this week.")
    assert not ok
    assert "toilet" in detail or "paper" in detail


def test_alike_face_titles_fail_and_different_titles_pass():
    same = _planet(
        perspectives=[
            {
                "title": "Trans Rights",
                "summary": "Trans people deserve rights.",
                "post_count": 20,
                "representative_posts": [{"text": "Trans rights are human rights.", "likes": 1}],
            },
            {
                "title": "Trans Rights 2",
                "summary": "The same claim again.",
                "post_count": 20,
                "representative_posts": [{"text": "Protect trans rights in law.", "likes": 1}],
            },
        ]
    )
    assert check_faces_different(same)

    different = _planet(
        perspectives=[
            {
                "title": "Iran War",
                "summary": "US war with Iran is unnecessary",
                "post_count": 10,
                "representative_posts": [
                    {"text": "A war with Iran is unnecessary.", "likes": 1},
                    {"text": "There is no reason for this war.", "likes": 1},
                ],
            },
            {
                "title": "Iran Attacks Ships",
                "summary": "Iran attacked ships",
                "post_count": 8,
                "representative_posts": [
                    {"text": "Iran attacked two ships in the strait.", "likes": 1},
                    {"text": "Missiles hit commercial ships overnight.", "likes": 1},
                ],
            },
        ]
    )
    assert check_faces_different(different) == []


def test_greeting_planet_is_junk_and_a_real_topic_is_not():
    greetings = _planet(
        name="Good Morning",
        category="Other",
        summary="Posts wish each other a good morning.",
        perspectives=[
            {
                "title": "Good Wishes",
                "summary": "People are saying good morning.",
                "post_count": 40,
                "representative_posts": [
                    {"text": "Good morning everyone, have a great day!", "likes": 1},
                    {"text": "Good morning friends!", "likes": 1},
                    {"text": "Morning! Hope your day is lovely.", "likes": 1},
                    {"text": "Good morning to you too.", "likes": 1},
                ],
            }
        ],
    )
    assert check_junk(greetings)
    assert check_junk(_planet()) == []


def test_missing_label_fails_and_a_real_label_passes():
    missing = _planet(name="", category="")
    reasons = check_label(missing)
    assert any("planet label missing" in reason for reason in reasons)
    assert any("section label missing" in reason for reason in reasons)
    assert check_label(_planet()) == []


def test_post_floor_uses_the_setting_and_zero_disables_it():
    small = _planet(post_count=8)
    assert check_post_floor(small, 30)
    assert check_post_floor(small, 5) == []
    assert check_post_floor(small, 0) == []


def test_thin_section_is_a_flag_not_a_planet_failure():
    payload = {
        "last_updated": "2026-10-19",
        "topics": [],
        "sections": {
            "World": [_planet(post_count=40), _planet(id="World-2", post_count=12)],
            "Sports": [_planet(id=f"Sports-{index}", post_count=40) for index in range(1, 11)],
        },
    }
    flags = thin_sections(payload, floor=30, catalog_size=10)
    assert [flag["section"] for flag in flags] == ["World"]
    report = check_edition(payload, SETTINGS)
    assert report["thin_sections"]
    assert report["planets"] == 12
    assert report["failure_counts"]["post_floor"] == 1
    assert report["passed"] == 11
    text = render_markdown(report)
    assert "Pass rate" in text
    assert "World" in text


def test_title_fit_requires_the_posts():
    empty = _planet(perspectives=[{"title": "Ukraine Sanctions", "summary": "A claim.", "post_count": 40}])
    assert check_title_fit(empty)


def test_a_trailing_number_and_a_dotted_acronym_still_fit():
    ok, _detail = title_fits("ADHD Struggles 2", "I have Real Bad ADHD and the struggles are daily.")
    assert ok
    ok, _detail = title_fits("US Sanctions", "The U.S. sanctions are the live argument.")
    assert ok


def test_each_failure_names_an_upstream_stage_and_the_edition_stays():
    payload = {
        "last_updated": "2026-10-19",
        "topics": [
            _planet(
                name="Good Morning",
                category="Other",
                summary="Posts wish each other a good morning.",
                post_count=8,
                perspectives=[
                    {
                        "title": "Good Wishes",
                        "summary": "People are saying good morning.",
                        "post_count": 4,
                        "representative_posts": [
                            {"text": "Good morning everyone, have a great day!", "likes": 1},
                            {"text": "Good morning friends!", "likes": 1},
                        ],
                    },
                    {
                        "title": "Good Wishes 2",
                        "summary": "The same wishes again.",
                        "post_count": 4,
                        "representative_posts": [
                            {"text": "Morning! Hope your day is lovely.", "likes": 1},
                            {"text": "Good morning to you too.", "likes": 1},
                        ],
                    },
                ],
            )
        ],
        "sections": {},
    }
    before = json.dumps(payload)
    report = check_edition(payload, SETTINGS, source="fixture")
    assert json.dumps(payload) == before
    assert report["detector_only"] is True
    assert report["floor_revisit"] is None
    assert report["failed"] == 1
    row = report["failures"][0]
    stages = {item["stage"] for item in row["checks"]}
    checks = {item["check"] for item in row["checks"]}
    assert "junk" in checks
    assert "ingest" in stages
    assert "post_floor" in checks
    assert "clustering/attach" in stages
    assert "faces_different" in checks
    assert "faces/stance" in stages
    text = render_markdown(report)
    assert "ingest" in text
    assert "does not change the edition" in text
    live_floor = check_edition(payload, {"min_planet_posts": 5, "catalog_size": 10})
    assert live_floor["failure_counts"]["post_floor"] == 0
    assert live_floor["floor_revisit"]["planets_under_shadow_floor"] == 1
    assert live_floor["floor_revisit"]["stage"] == "clustering/attach"
    assert json.dumps(payload) == before


def test_report_round_trip_counts():
    payload = {
        "last_updated": "2026-10-19",
        "topics": [_planet()],
        "sections": {"World": [_planet()]},
    }
    report = check_edition(payload, SETTINGS, source="fixture", source_commit="abc")
    assert report["planets"] == 2
    assert report["failed"] == 0
    assert report["pass_rate"] == 1.0
    loaded = json.loads(json.dumps(report))
    assert loaded["passed"] + loaded["failed"] == loaded["planets"]
