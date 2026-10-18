"""Free filter for automated NWS-style weather alert bots (#228).

Human posts about weather or climate are not bots. Handles and wire text
shapes from the live Environment audit (nws-bot, weather.im, IEMbot).
"""

from __future__ import annotations

import os
import re

from pipeline.spam_guard import post_body

_PURGE_STORED_WEATHER_ENV = "PERSPECTIVERSE_PURGE_STORED_WEATHER"


def purge_stored_weather_enabled() -> bool:
    """Whether ``drop_non_quality_posts`` may delete stored weather-bot rows.

    Default is off. New weather-bot posts are still refused at ingest and kept
    out of the edition via ``edition_posts_for_clustering`` either way.
    """
    raw = os.environ.get(_PURGE_STORED_WEATHER_ENV)
    if raw is None or not str(raw).strip():
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}

# Bluesky handles for NWS mirrors and IEM hazardous-weather bots.
_BOT_HANDLE_RE = re.compile(
    r"(?:"
    r"nws-bot"
    r"|\.weather\.im\b"
    r"|iembot"
    r"|iem\.mesonet"
    r"|wxbot"
    r")",
    re.IGNORECASE,
)

# ``AMA updates Severe Thunderstorm Warning … till 6:45 PM CDT``.
_ALERT_WIRE_RE = re.compile(
    r"\b(?:severe|special|flash\s+flood|tornado|winter\s+storm|excessive\s+rainfall|"
    r"hazardous\s+weather|hydrologic\s+outlook|flood\s+warning|thunderstorm\s+warning|"
    r"weather\s+alert)\b"
    r".{0,220}?"
    r"\b(?:until|till|expires?|valid|in\s+effect)\b"
    r".{0,120}?"
    r"\b(?:CDT|CST|EDT|EST|MDT|MST|PST|PDT|UTC)\b",
    re.IGNORECASE | re.DOTALL,
)

# Issued-line bots without a timezone still match when the handle is a bot.
_ISSUED_ALERT_RE = re.compile(
    r"\b(?:updates?|issued|continues)\b.{0,60}\b(?:severe|special|flash|tornado|winter|excessive|hazardous|thunderstorm)\b",
    re.IGNORECASE,
)


def weather_bot_reason(post: dict) -> str | None:
    """Return a block reason, or None when the post is not an alert bot."""
    author = str(post.get("author") or "")
    text = post_body(post)
    if not text.strip():
        return None
    if _BOT_HANDLE_RE.search(author):
        return "weather_bot"
    lowered = text.lower()
    if "nws-bot" in lowered or ".weather.im" in lowered:
        return "weather_bot"
    if _ALERT_WIRE_RE.search(text):
        return "weather_bot"
    if _BOT_HANDLE_RE.search(text) and _ISSUED_ALERT_RE.search(text):
        return "weather_bot"
    return None
