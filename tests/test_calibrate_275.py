"""The #275 calibration uses that sheet's yes/no rows, not leaked face pairs."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calibrate_275_labels.py"
_SPEC = importlib.util.spec_from_file_location("calibrate_275_labels", _PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
calibration_rows = _MODULE.calibration_rows
percentage_withheld = _MODULE.percentage_withheld
render_level = _MODULE.render_level
duplicate_kind = _MODULE.duplicate_kind
kind_recall = _MODULE.kind_recall
recall_is_near_zero = _MODULE.recall_is_near_zero
render_kind_recall = _MODULE.render_kind_recall


def _design():
    def bands(shares):
        return [{"band": name, "share": share, "pairs": 1} for name, share in shares.items()]

    return {
        "planets": {
            "headline": {"bands": bands({"B0": 0.7, "B1": 0.3})},
            "sample": [{"pair_id": "p001", "band": "B0"}, {"pair_id": "p002", "band": "B1"}],
        },
        "faces": {
            "headline": {"bands": bands({"B1": 0.11, "B3": 0.52})},
            "sample": [
                {"pair_id": "f001", "band": "B3"},
                {"pair_id": "f002", "band": "B0"},
            ],
        },
    }


def test_face_calibration_drops_leaks_and_unsure():
    labeled = [
        {"pair_id": "p001", "level": "planet", "title_a": "A", "title_b": "B", "is_duplicate": "yes"},
        {"pair_id": "p002", "level": "planet", "title_a": "C", "title_b": "D", "is_duplicate": "unsure"},
        {"pair_id": "c001", "level": "face_census", "band": "B3", "title_a": "E", "title_b": "F", "is_duplicate": "no"},
        {"pair_id": "f008", "level": "planet_leak", "title_a": "G", "title_b": "H", "is_duplicate": "yes"},
    ]
    design = _design()
    planets = calibration_rows(labeled, design, level="planet")
    faces = calibration_rows(labeled, design, level="face")
    assert [row["pair_id"] for row in planets["rows"]] == ["p001"]
    assert planets["unsure"] == 1
    assert [row["pair_id"] for row in faces["rows"]] == ["c001"]
    assert faces["excluded_leak"] == 1
    assert faces["missing_population_bands"] == ["B1"]
    assert faces["rows"][0]["band_share"] == "0.52"


def test_face_percentage_is_withheld_below_30_held_out_pairs():
    assert percentage_withheld(9) is True
    assert percentage_withheld(29) is True
    assert percentage_withheld(30) is False
    rendered = "\n".join(
        render_level(
            "Faces",
            {
                "tuned_threshold": {"title_min": 0.5, "centroid_min": 0.9, "tune_f1": 0.2},
                "split": {"seed": 273, "tuned_on": 18, "holdout": 9, "spot_checks": 0},
                "headline": {
                    "weighted": False,
                    "precision": None,
                    "recall": None,
                    "counts_only": True,
                    "agree": 8,
                    "judged": 9,
                    "held_out": 9,
                    "withheld_because": "Held-out set is 9, under 30. No face percentage.",
                },
                "bands": [
                    {
                        "band": "B3",
                        "share": 0.52,
                        "matched": 9,
                        "true_positive": 5,
                        "true_negative": 3,
                        "precision": 0.5,
                        "recall": 0.5,
                    }
                ],
                "matched": 9,
                "unmatched": 0,
            },
        )
    )
    assert "8 of 9 agree" in rendered
    assert "No face percentage" in rendered
    assert "precision" not in rendered


def _scored(pair_type, left, right, *, near):
    return {
        "pair_type": pair_type,
        "left_title": left,
        "right_title": right,
        "near_duplicate": near,
        "titles_alike": near,
        "centroid_cosine": 0.95 if near else 0.2,
    }


def test_kind_recall_is_raw_counts_and_names_a_cheap_tracker_when_near_zero():
    assert duplicate_kind(
        {"level": "planet", "title_a": "Good Day", "title_b": "Happy Sunday", "is_duplicate": "yes"}
    ) == "greeting"
    assert duplicate_kind(
        {"level": "planet", "title_a": "AI Control", "title_b": "AI bots", "is_duplicate": "yes"}
    ) == "same_story"
    assert duplicate_kind(
        {"level": "face_census", "title_a": "Show Quality", "title_b": "Show Enjoyment", "is_duplicate": "yes"}
    ) == "paraphrase_face"
    assert duplicate_kind(
        {"level": "planet_leak", "title_a": "Good Day", "title_b": "Happy Sunday", "is_duplicate": "yes"}
    ) is None
    assert duplicate_kind(
        {"level": "planet", "title_a": "Good Day", "title_b": "Happy Sunday", "is_duplicate": "unsure"}
    ) is None
    assert recall_is_near_zero(0, 11) is True
    assert recall_is_near_zero(1, 9) is True
    assert recall_is_near_zero(8, 13) is False
    assert recall_is_near_zero(0, 0) is False

    rows = [
        {"pair_id": "p010", "level": "planet", "title_a": "Great Day", "title_b": "Happy Sunday", "is_duplicate": "yes"},
        {"pair_id": "p002", "level": "planet", "title_a": "Good Day", "title_b": "Hope For The Day", "is_duplicate": "yes"},
        {"pair_id": "p041", "level": "planet", "title_a": "AI Control", "title_b": "AI bots", "is_duplicate": "yes"},
        {"pair_id": "c007", "level": "face_census", "title_a": "Show Quality", "title_b": "Show Enjoyment", "is_duplicate": "yes"},
        {"pair_id": "f018", "level": "planet_leak", "title_a": "Great Day", "title_b": "Glad Returns", "is_duplicate": "yes"},
    ]
    scored = [
        _scored("planet", "Great Day", "Happy Sunday", near=False),
        _scored("planet", "Good Day", "Hope For The Day", near=False),
        _scored("planet", "AI Control", "AI bots", near=False),
        _scored("face", "Show Quality", "Show Enjoyment", near=False),
    ]
    report = kind_recall(rows, scored)
    by_label = {kind["label"]: kind for kind in report["kinds"]}
    assert by_label["Greeting/chit-chat planets (#288)"]["flagged"] == 0
    assert by_label["Greeting/chit-chat planets (#288)"]["total"] == 2
    assert "greeting-title count" in by_label["Greeting/chit-chat planets (#288)"]["tracker"]
    assert by_label["Same-story fragments (#287)"]["flagged"] == 0
    assert by_label["Same-story fragments (#287)"]["total"] == 1
    assert "under 20 posts" in by_label["Same-story fragments (#287)"]["tracker"]
    assert by_label["Paraphrase faces (#286)"]["flagged"] == 0
    assert by_label["Paraphrase faces (#286)"]["total"] == 1
    assert "stance-agreement count" in by_label["Paraphrase faces (#286)"]["tracker"]
    assert by_label["Other"]["total"] == 0
    assert by_label["Other"]["tracker"] is None
    rendered = "\n".join(render_kind_recall(report))
    assert "0 of 2" in rendered
    assert "0 of 1" in rendered
    assert "greeting-title count" in rendered
    assert "stance-agreement count" in rendered
