"""Politics section sanity (#228)."""

from pipeline.section_sanity import (
    members_support_politics,
    partition_politics_planets,
    politics_planet_destination,
)


def test_music_video_planet_moves_to_culture():
    members = [
        {"text": "youtu.be/VAWjsVoDpm0?si=abc #musicsky"},
        {"text": "Music for Mori boosting youtu.be/xyz123 #musicsky"},
        {"text": "youtu.be/another?feature=share"},
    ]
    assert members_support_politics(members, name="Music Videos") is False
    assert politics_planet_destination("Music Videos", members) == "Culture"


def test_tax_meme_moves_to_culture_real_policy_stays():
    meme = [
        {"text": "Die Hard for Tax Purposes"},
        {"text": "Catch Me If You Can for Tax Purposes"},
        {"text": "Add for Tax Purposes to a movie title"},
    ]
    policy = [
        {"text": "The Senate tax bill would raise brackets on households over $400k."},
        {"text": "IRS enforcement funding is the real fight in this Congress vote."},
    ]
    assert politics_planet_destination("Tax Movie Titles", meme) == "Culture"
    assert politics_planet_destination("Tax Purposes", meme) == "Culture"
    assert members_support_politics(policy, name="Tax Bill") is True


def test_thank_you_planet_moves_to_other():
    members = [
        {"text": "Thank you all for such an AMAZING day!"},
        {"text": "Thank you so much ❤️"},
        {"text": "Thanks everyone who showed up!"},
    ]
    assert politics_planet_destination("Thank You", members) == "Other"


def test_partition_politics_planets_splits_topics():
    posts = [{"uri": "a", "text": "youtu.be/x #musicsky"}, {"uri": "b", "text": "youtu.be/y"}]
    topics = [
        {
            "name": "Music Videos",
            "post_count": 2,
            "_member_uris": ["a", "b"],
            "category": "Politics",
        },
        {
            "name": "Senate Vote",
            "post_count": 1,
            "_member_uris": [],
            "category": "Politics",
            "perspectives": [
                {
                    "representative_posts": [
                        {"text": "Congress should publish mail ballot rules before November."}
                    ]
                }
            ],
        },
    ]
    kept, moved = partition_politics_planets(topics, posts)
    assert len(kept) == 1
    assert kept[0]["name"] == "Senate Vote"
    assert "Culture" in moved
    assert moved["Culture"][0]["name"] == "Music Videos"
