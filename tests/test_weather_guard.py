"""Weather alert bot filter (#228)."""

from pipeline.chitchat_guard import edition_posts_for_clustering, ingest_block_reason
from pipeline.store import should_drop_stored_post
from pipeline.stored_purge import purge_stored_reasons_list
from pipeline.weather_guard import weather_bot_reason

_BOT = {
    "author": "ama.nws-bot.us",
    "text": "AMA updates Severe Thunderstorm Warning till 6:45 PM CDT.",
}


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


def test_stored_weather_rows_purge_only_when_reason_listed(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)
    assert purge_stored_reasons_list() == frozenset()
    assert ingest_block_reason(_BOT) == "weather_bot"
    assert should_drop_stored_post(_BOT) is False

    monkeypatch.setenv("PERSPECTIVERSE_PURGE_STORED_REASONS", "weather_bot")
    assert "weather_bot" in purge_stored_reasons_list()
    assert should_drop_stored_post(_BOT) is True


def test_stored_weather_stays_out_of_edition_when_not_listed(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)
    kept, _lang, _links, _chit = edition_posts_for_clustering([_BOT])
    assert kept == []


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
