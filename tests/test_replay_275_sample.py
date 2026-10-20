"""The Oct 19 pair sheet must match its buckets before a labeler sees it."""

from __future__ import annotations

import pytest

from scripts.replay_275_oct19 import SampleSheetError, _draw, validate_label_sheet


def _planet(pair_id: str, left: str, right: str, section: str = "Other") -> dict:
    return {
        "pair_id": pair_id,
        "level": "planet",
        "section": section,
        "planet_a": left,
        "planet_b": right,
        "title_a": left,
        "title_b": right,
        "same_planet": False,
        "band": "B2",
    }


def _face(pair_id: str, planet: str, left: str, right: str, section: str = "Culture") -> dict:
    return {
        "pair_id": pair_id,
        "level": "face",
        "section": section,
        "planet_a": planet,
        "planet_b": planet,
        "title_a": left,
        "title_b": right,
        "same_planet": True,
        "band": "B3",
    }


def test_valid_sheet_passes():
    validate_label_sheet(
        [
            _planet("p001", "Great Day", "Happy Sunday"),
            _face("f001", "The Show", "Show Quality", "Show Enjoyment"),
        ]
    )


def test_face_row_rejects_cross_planet_pair():
    leaked = _face("f018", "Great Day", "Great Day", "Glad Returns")
    leaked["planet_b"] = "Glad Returns"
    leaked["same_planet"] = False
    with pytest.raises(SampleSheetError, match="f018"):
        validate_label_sheet([leaked])


def test_face_row_rejects_same_title_and_missing_flag():
    same_title = _face("f002", "The Show", "Show Quality", "Show Quality")
    missing_flag = _face("f003", "The Show", "Show Quality", "Show Enjoyment")
    missing_flag["same_planet"] = False
    with pytest.raises(SampleSheetError, match="two distinct faces"):
        validate_label_sheet([same_title])
    with pytest.raises(SampleSheetError, match="same_planet true"):
        validate_label_sheet([missing_flag])


def test_planet_row_rejects_one_planet_or_two_sections():
    same = _planet("p002", "Good Day", "Good Day")
    split = _planet("p003", "US Iran War", "Russia Sanctions", section="World|Business")
    with pytest.raises(SampleSheetError, match="two different planets"):
        validate_label_sheet([same])
    with pytest.raises(SampleSheetError, match="one section"):
        validate_label_sheet([split])


def test_duplicate_endpoints_fail_including_a_face_copy_of_a_planet():
    planet = _planet("p001", "Great Day", "Glad Returns")
    copy = _face("f018", "Great Day", "Great Day", "Glad Returns", section="Other")
    copy["planet_b"] = "Glad Returns"
    copy["same_planet"] = True
    with pytest.raises(SampleSheetError, match="duplicates p001"):
        validate_label_sheet([planet, copy])


def test_duplicate_pair_id_fails():
    with pytest.raises(SampleSheetError, match="duplicate pair id"):
        validate_label_sheet(
            [
                _planet("p001", "Great Day", "Happy Sunday"),
                _planet("p001", "US Iran War", "Russia Sanctions", section="World"),
            ]
        )


def test_census_is_within_planet_and_stable():
    from scripts.replay_275_oct19 import _census_sheet

    rows = [
        _face("x", "Zebra", "B", "A", section="World"),
        _face("y", "Alpha", "M", "N", section="Business"),
        {
            **_planet("z", "Great Day", "Glad Returns"),
            "level": "face",
            "same_planet": False,
            "title_a": "Great Day",
            "title_b": "Glad Returns",
        },
    ]
    census = _census_sheet(rows)
    assert [row["pair_id"] for row in census] == ["c001", "c002"]
    assert census[0]["section"] == "Business"
    assert all(row["is_duplicate"] == "" for row in census)
    validate_label_sheet(census)


def test_other_day_cannot_overwrite_the_oct19_yardstick(tmp_path):
    from scripts.replay_275_oct19 import OCT19_PAIRS, _guard_edition_outputs

    blocked = _guard_edition_outputs("2026-10-20", OCT19_PAIRS, tmp_path / "design.json")
    assert blocked and "Oct 19 yardstick" in blocked
    blocked_design = _guard_edition_outputs(
        "2026-10-19",
        tmp_path / "oct19-pairs.csv",
        OCT19_PAIRS.with_name("oct19-sample-design.json"),
    )
    assert blocked_design and "oct19-sample-design.json" in blocked_design


def test_merge_bar_leaves_grok_columns_empty_and_counts_drops():
    from scripts.replay_275_score import merge_bar_rows

    rows = merge_bar_rows(
        {
            "oct19": {
                "edition": "2026-10-19",
                "planets": [
                    {"section": "Other", "name": "Happy Sunday", "posts": 6, "daypart_gate_drops": True},
                    {"section": "Politics", "name": "Fascism", "posts": 201, "daypart_gate_drops": False},
                ],
            },
            "oct20": {"edition": "2026-10-20", "planets": []},
        }
    )
    scored = [row for row in rows if row["fix_id"] != "published_edition_not_a_275_fix"]
    assert scored
    assert all(row["good_labeled_duplicates_removed_or_joined"] == "" for row in scored)
    assert all(row["over_merge_labeled_different"] == "" for row in scored)
    assert all(row["scorer"] == "awaiting grok-4.7" for row in scored)
    gate = next(row for row in rows if row["fix_id"] == "daypart_planet_gate" and row["day"] == "2026-10-19")
    assert gate["dropped_planets"] == 1 and gate["dropped_posts"] == 6
    assert gate["moved_to_other_planets"] == 0
    assert gate["verdict"].startswith("fails (c)")
    assert "Politics" not in gate["per_section"]
    fix1 = next(row for row in rows if row["fix_id"] == "fix1_paraphrase_face" and row["day"] == "2026-10-20")
    assert fix1["dropped_planets"] == 0 and fix1["moved_to_other_planets"] == 0


def test_face_draw_keeps_only_same_planet_pairs():
    rows = [
        {**_face("x", "The Show", "Show Quality", "Show Enjoyment"), "band": "B3"},
        {
            **_planet("y", "Great Day", "Glad Returns"),
            "level": "face",
            "same_planet": False,
            "band": "B3",
            "title_a": "Great Day",
            "title_b": "Glad Returns",
        },
    ]
    drawn = _draw(rows, prefix="f", require_same_planet=True)
    assert [row["title_a"] for row in drawn] == ["Show Quality"]
    assert all(row["same_planet"] is True and row["planet_a"] == row["planet_b"] for row in drawn)
    validate_label_sheet(drawn)
