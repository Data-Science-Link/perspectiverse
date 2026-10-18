"""Weather alert bot filter (#228)."""

from pipeline.chitchat_guard import ingest_block_reason
from pipeline.weather_guard import weather_bot_reason


def test_nws_handle_and_warning_wire_are_blocked():
    bot = {
        "author": "ama.nws-bot.us",
        "text": (
            "AMA updates Severe Thunderstorm Warning for portions of the area "
            "till 6:45 PM CDT at Tue, 13 Oct 2026."
        ),
    }
    assert weather_bot_reason(bot) == "weather_bot"
    assert ingest_block_reason(bot) == "weather_bot"


def test_iem_bot_outlook_is_blocked():
    post = {
        "author": "iembot",
        "text": "Hazardous Weather Outlook issued for central Iowa through Wednesday evening.",
    }
    assert weather_bot_reason(post) == "weather_bot"


def test_human_weather_and_climate_discussion_passes():
    climate = {
        "author": "atoms-ok",
        "text": "If your climate plan needs weather to cooperate, it is a hope, not a grid.",
    }
    personal = {
        "author": "local",
        "text": "It was like 50 degrees here yesterday. We ran the whole weather playbook.",
    }
    assert weather_bot_reason(climate) is None
    assert weather_bot_reason(personal) is None
    assert ingest_block_reason(climate) is None
    assert ingest_block_reason(personal) is None
