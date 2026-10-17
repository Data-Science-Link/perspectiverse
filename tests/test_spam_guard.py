"""Free spam guard. No network."""

from pipeline.spam_guard import guard_reason, partition_guard


def test_radio_bot_and_crypto_ticker_are_spam():
    radio = {
        "text": "Now playing on KB Radio: Fantasy by Aldo Nova! Tune in now: https://www.kbradio.online",
    }
    ticker = {"text": "ACCUMULATED $10,126 of NEAR. Price: $4.89 on the 15m chart."}
    assert guard_reason(radio) == "promo"
    assert guard_reason(ticker) == "crypto"


def test_ordinary_remark_and_news_link_pass():
    remark = {
        "text": "Yes, this is treason. But going forward we should stop relying on one satellite vendor.",
    }
    news = {
        "text": "State lawmakers push for stronger bail laws in Pennsylvania https://www.wtae.com/article/pennsylvania-bail-laws/74137826",
    }
    short = {"text": "He does say the stupidest things."}
    assert guard_reason(remark) is None
    assert guard_reason(news) is None
    assert guard_reason(short) is None


def test_non_claim_aside_is_not_spam():
    aside = {"text": "Me: why am I so restless. Also me: I forgot to buy antihistamines."}
    assert guard_reason(aside) is None


def test_store_bots_and_giveaways_are_spam():
    giveaway = {"text": "Enter to win an Ang Hill Capsule Wardrobe! wn.nr/w2gBZL2"}
    book = {"text": "Available in paperback or Kindle Unlimited: www.amazon.com/dp/B0DWMYX8WF"}
    listing = {"text": "Still available on eBay www.ebay.com/itm/298123 The Big Heat DVD."}
    trial = {"text": "Free trial, deals from your airport: cheapweekendflights.co.uk/b?c=b"}
    chart = {"text": "NEAR is up on the 15m chart after the open."}
    bot = {
        "text": "The news at 04:37:57 is: Army chief says politicians should prepare for war. #news",
    }
    assert guard_reason(giveaway) == "promo"
    assert guard_reason(book) == "promo"
    assert guard_reason(listing) == "promo"
    assert guard_reason(trial) == "promo"
    assert guard_reason(chart) == "crypto"
    assert guard_reason(bot) == "bot"


def test_political_speech_and_a_wishlist_pass():
    vote = {
        "text": "Vote like your social security is on the line. Elect Dan Schwartz. #VOTE",
    }
    news = {
        "text": "Musk settles election lottery lawsuits over $1 million voter giveaways - The Hill",
    }
    wishlist = {
        "text": "I have a wish list. It would be nice to receive books. www.amazon.com/hz/wishlist/ls/1",
    }
    aid = {"text": "Heart patient has been facing eviction gofund.me/96156d0a9"}
    assert guard_reason(vote) is None
    assert guard_reason(news) is None
    assert guard_reason(wishlist) is None
    assert guard_reason(aid) is None


def test_center_now_is_not_an_enter_now_solicitation():
    remark = {"text": "The presidential center now costs three times the estimate."}
    idiom = {"text": "The text of the note is the clearest giveaway that the note is fake."}
    assert guard_reason(remark) is None
    assert guard_reason(idiom) is None


def test_partition_counts_blocks():
    posts = [
        {"text": "Congress should publish the mail ballot rules before November."},
        {"text": "OnlyFans link in bio, dm me for the menu."},
    ]
    kept, blocked = partition_guard(posts)
    assert len(kept) == 1
    assert blocked[0][1] == "promo"
