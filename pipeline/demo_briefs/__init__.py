"""Hand-written face briefs for the synthetic solar system.

Featured planets keep their posts in generate_demo_data.py and take core arguments
from featured.py. Every other roster planet is filled from these category modules.
"""

from __future__ import annotations

from pipeline.demo_briefs.economy import BRIEFS as ECONOMY
from pipeline.demo_briefs.education import BRIEFS as EDUCATION
from pipeline.demo_briefs.entertainment import BRIEFS as ENTERTAINMENT
from pipeline.demo_briefs.environment import BRIEFS as ENVIRONMENT
from pipeline.demo_briefs.featured import FEATURED_ARGUMENTS
from pipeline.demo_briefs.health import BRIEFS as HEALTH
from pipeline.demo_briefs.media import BRIEFS as MEDIA
from pipeline.demo_briefs.politics import BRIEFS as POLITICS
from pipeline.demo_briefs.religion import BRIEFS as RELIGION
from pipeline.demo_briefs.sports import BRIEFS as SPORTS
from pipeline.demo_briefs.technology import BRIEFS as TECHNOLOGY

FACE_BRIEFS = {
    **TECHNOLOGY,
    **ECONOMY,
    **POLITICS,
    **ENVIRONMENT,
    **HEALTH,
    **ENTERTAINMENT,
    **SPORTS,
    **EDUCATION,
    **MEDIA,
    **RELIGION,
}

__all__ = ["FACE_BRIEFS", "FEATURED_ARGUMENTS"]
