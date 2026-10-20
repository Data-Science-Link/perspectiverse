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
