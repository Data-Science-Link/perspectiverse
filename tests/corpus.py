"""Separable corpus for the lexical clusterer. Ten topics, six faces, plus noise."""

from __future__ import annotations

TOPICS = (
    "climate",
    "housing",
    "vaccine",
    "election",
    "football",
    "privacy",
    "tuition",
    "headline",
    "wage",
    "software",
)
FACES = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")


def build_tiny_posts() -> list[dict]:
    posts: list[dict] = []
    for topic in TOPICS:
        for face_index, face in enumerate(FACES):
            for copy in range(2):
                likes = 100 - face_index * 10 + copy
                posts.append(
                    {
                        "uri": f"at://fixture/{topic}/{face}/{copy}",
                        "author": f"{topic}.{face}.{copy}",
                        "text": f"{topic} {topic} {topic} {topic} {face} {face} {face}",
                        "likes": likes,
                        "created_at": "2026-09-25T12:00:00Z",
                    }
                )
    for copy in range(2):
        posts.append(
            {
                "uri": f"at://fixture/noise/{copy}",
                "author": f"noise.{copy}",
                "text": f"zzzznoise zzzznoise zzzznoise outlier {copy} extra words here",
                "likes": 1,
                "created_at": "2026-09-25T12:00:00Z",
            }
        )
    return posts
