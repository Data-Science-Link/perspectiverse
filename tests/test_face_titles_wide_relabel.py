"""Wide relabel must keep main publish coverage (loose stems), not strict reporting."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from pipeline import live
from pipeline.face_titles import repair_payload_face_titles
from pipeline.story_attach import merge_alike_published_faces

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "face_titles_snapshot.json"


def _post(uri: str, text: str, likes: int = 1) -> dict:
    return {"uri": uri, "author": "u", "clean_text": text, "text": text, "likes": likes}


def test_wide_relabel_keeps_named_title_when_loose_coverage_passes(monkeypatch):
    posts = [
        _post("1", "Trans rights are under attack in every state legislature.", 5),
        _post("2", "Protect trans rights and trans kids in schools.", 4),
        _post("3", "Weather forecast unrelated to politics.", 1),
    ]
    face_posts = posts
    face_cosines = [0.9, 0.8, 0.2]
    context = {
        "backend": None,
        "model": None,
        "prompt_sample_size": 40,
        "limit": 6,
    }

    def fake_label(*_args, **_kwargs):
        return {
            "title": "Trans Rights",
            "summary": "The posts defend trans rights against political attacks.",
            "arguments": [
                "Trans rights are under attack in every state legislature.",
                "Protect trans rights and trans kids in schools.",
            ],
        }

    monkeypatch.setattr(live, "label_perspective", fake_label)
    wide = live._wide_label_face_from_posts(
        face_posts,
        None,
        face_cosines,
        ["trans", "rights"],
        context,
        limit=6,
    )
    assert wide["title"] == "Trans Rights"


def test_fixture_titles_unchanged_except_exact_duplicate_merge():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original_titles: dict[tuple[str, str], str] = {}
    for planet in list(data.get("topics") or []) + sum(
        (data.get("sections") or {}).values(),
        [],
    ):
        name = str(planet.get("name") or "")
        for face in planet.get("perspectives") or []:
            original_titles[(name, str(face.get("id") or ""))] = str(face.get("title") or "")

    merged_only = copy.deepcopy(data)
    for block in (merged_only.get("topics") or [], * (merged_only.get("sections") or {}).values()):
        merge_alike_published_faces(list(block))

    repaired = copy.deepcopy(data)
    repair_payload_face_titles(repaired)

    def iter_planets(payload: dict):
        for planet in payload.get("topics") or []:
            yield planet
        for planets in (payload.get("sections") or {}).values():
            for planet in planets:
                yield planet

    for planet_m, planet_r in zip(iter_planets(merged_only), iter_planets(repaired)):
        assert str(planet_m.get("name")) == str(planet_r.get("name"))
        for face_m, face_r in zip(
            planet_m.get("perspectives") or [],
            planet_r.get("perspectives") or [],
        ):
            assert face_m.get("title") == face_r.get("title")

    wwii = next(p for p in iter_planets(repaired) if p.get("name") == "WWII Veterans")
    assert len(wwii.get("perspectives") or []) == 1
    assert original_titles[("WWII Veterans", "World-7A")] == original_titles[("WWII Veterans", "World-7B")]
