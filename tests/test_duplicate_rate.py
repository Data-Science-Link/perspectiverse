"""Duplicate rate: guards, and a tune/holdout split that does not grade itself."""

import json

from pipeline.duplicate_rate import (
    SPLIT_SEED,
    agreement_with_labels,
    apply_post_hoc_guards,
    duplicate_rates,
    split_labeled_sample,
    tune_threshold,
)


def _planet(name, texts, *, post_count=40, face_title=None):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "category": "World",
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


def _edition(*planets):
    return {"last_updated": "2026-10-19", "topics": [], "sections": {"World": list(planets)}}


def test_guards_are_a_copy_and_drop_junk_and_the_floor():
    greet = _planet(
        "Good Morning",
        [
            "Good morning everyone, have a great day!",
            "Good morning friends!",
            "Morning! Hope your day is lovely.",
            "Good morning to you too.",
        ],
        post_count=40,
    )
    tiny = _planet("Tiny Speck", ["One short note about a harbor crane."], post_count=4)
    oil = _planet(
        "Oil Prices",
        ["Brent crude rose after the supply cut.", "Oil prices climbed on the Brent contract."],
        post_count=40,
    )
    payload = _edition(greet, tiny, oil)
    original = json.dumps(payload)
    guarded, removed = apply_post_hoc_guards(payload, floor=30)
    assert json.dumps(payload) == original
    assert removed["floor"] == 1
    assert removed["junk"] == 1
    names = [planet["name"] for planet in guarded["sections"]["World"]]
    assert names == ["Oil Prices"]


def test_face_fold_keeps_string_planet_ids():
    planet = _planet(
        "Harbor Strike",
        ["Dock workers walked out at the harbor."],
        post_count=40,
    )
    planet["id"] = "World-7"
    planet["perspectives"] = [
        {
            "id": "a",
            "title": "Night Shift",
            "post_count": 20,
            "representative_posts": [{"text": "The night shift walked out.", "likes": 1}],
        },
        {
            "id": "b",
            "title": "Night Shift",
            "post_count": 20,
            "representative_posts": [{"text": "Night shift workers left the dock.", "likes": 1}],
        },
    ]
    guarded, removed = apply_post_hoc_guards(_edition(planet), floor=5)
    kept = guarded["sections"]["World"][0]
    assert kept["id"] == "World-7"
    assert len(kept["perspectives"]) == 1
    assert removed["faces_folded"] == 1


def test_before_rate_stays_when_the_floor_removes_a_duplicate():
    left = _planet("Widget Recall", ["The widget recall covers the same batch.", "Recall notices name the same widget."], post_count=8)
    right = _planet("Widget Recall 2", ["The widget recall covers the same batch.", "Recall notices name the same widget."], post_count=8)
    other = _planet("Harbor Strike", ["Dock workers walked out at the harbor.", "The harbor strike stopped the night shift."], post_count=40)
    report = duplicate_rates(_edition(left, right, other), floor=30, labeled_path=__file__ and _missing())
    before = report["before"]["planets"]
    after = report["after"]["planets"]
    assert before["near_duplicates"] >= 1
    assert after["near_duplicates"] == 0
    assert before["rate"] > after["rate"]
    assert report["agreement"]["present"] is False


def _missing():
    from pathlib import Path

    return Path("/tmp/no-such-oct19-pairs.csv")


def test_split_keeps_spot_checks_out_of_the_tune_set():
    labels = []
    for index in range(9):
        labels.append(
            {
                "pair_type": "planet",
                "left_key": f"planet:World:{index}",
                "right_key": f"planet:World:{index + 100}",
                "left_title": f"Left {index}",
                "right_title": f"Right {index}",
                "duplicate": "1" if index % 2 == 0 else "0",
                "spot_check": "1" if index >= 6 else "0",
            }
        )
    first = split_labeled_sample(labels, seed=SPLIT_SEED)
    second = split_labeled_sample(list(reversed(labels)), seed=SPLIT_SEED)
    assert [row["left_key"] for row in first["tune"]] == [row["left_key"] for row in second["tune"]]
    assert len(first["tune"]) == 4
    assert len(first["holdout"]) == 2
    assert len(first["spot_checks"]) == 3
    tune_ids = {row["left_key"] for row in first["tune"]}
    eval_ids = {row["left_key"] for row in first["evaluation"]}
    assert tune_ids.isdisjoint(eval_ids)
    assert all(row["spot_check"] == "1" for row in first["spot_checks"])


def test_agreement_is_not_scored_on_the_tune_pairs(tmp_path):
    """Holdout labels disagree with the tune labels. The reported score follows the holdout."""
    labels = []
    scored = []
    for index in range(6):
        left = f"planet:World:{index}"
        right = f"planet:World:{index + 20}"
        # Deterministic split of a sorted pool of 6 is 4 tune and 2 holdout.
        # Give every pair the same scores so the threshold cannot tell them apart,
        # then check the agreement counts only the evaluation rows.
        labels.append(
            {
                "pair_type": "planet",
                "left_key": left,
                "right_key": right,
                "left_title": f"Alpha {index}",
                "right_title": f"Beta {index}",
                "duplicate": "1",
                "spot_check": "0",
            }
        )
        scored.append(
            {
                "pair_type": "planet",
                "left_key": left,
                "right_key": right,
                "left_title": f"Alpha {index}",
                "right_title": f"Beta {index}",
                "title_similarity": 0.2,
                "titles_alike": False,
                "centroid_cosine": 0.99,
                "near_duplicate": False,
            }
        )
    labels.append(
        {
            "pair_type": "planet",
            "left_key": "planet:World:spot",
            "right_key": "planet:World:spot-b",
            "left_title": "Spot Left",
            "right_title": "Spot Right",
            "duplicate": "0",
            "spot_check": "1",
        }
    )
    scored.append(
        {
            "pair_type": "planet",
            "left_key": "planet:World:spot",
            "right_key": "planet:World:spot-b",
            "left_title": "Spot Left",
            "right_title": "Spot Right",
            "title_similarity": 0.2,
            "titles_alike": False,
            "centroid_cosine": 0.99,
            "near_duplicate": False,
        }
    )
    parts = split_labeled_sample(labels)
    tuned = tune_threshold(scored, parts["tune"])
    # The tune rows are all duplicates at cosine 0.99, so the chosen cut flags them.
    assert tuned["centroid_min"] <= 0.99
    flagged = []
    for pair in scored:
        flagged.append({**pair, "near_duplicate": pair["centroid_cosine"] >= tuned["centroid_min"]})
    measured = agreement_with_labels(flagged, parts["evaluation"])
    assert measured["matched"] == len(parts["evaluation"])
    assert measured["matched"] == len(parts["holdout"]) + len(parts["spot_checks"])
    # Scoring the tune rows as well would add four more matches.
    leaked = agreement_with_labels(flagged, parts["tune"] + parts["evaluation"])
    assert leaked["matched"] == measured["matched"] + len(parts["tune"])
    assert measured["matched"] != leaked["matched"]

    path = tmp_path / "oct19-pairs.csv"
    path.write_text(
        "pair_type,left_key,right_key,left_title,right_title,duplicate,spot_check\n"
        + "\n".join(
            f"{row['pair_type']},{row['left_key']},{row['right_key']},{row['left_title']},{row['right_title']},{row['duplicate']},{row['spot_check']}"
            for row in labels
        )
        + "\n",
        encoding="utf-8",
    )
    report = duplicate_rates(_edition(_planet("Only", ["A single harbor story about wages."])), labeled_path=path, floor=5)
    assert report["agreement"]["tuned_on"] == len(parts["tune"])
    assert report["agreement"]["scored_on"] == len(parts["evaluation"])
    assert report["agreement"]["spot_checks"] == 1
    assert report["agreement"]["tuned_on"] + report["agreement"]["holdout"] + report["agreement"]["spot_checks"] == len(labels)
