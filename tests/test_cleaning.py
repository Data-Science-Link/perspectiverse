from pipeline.cleaning import clean_posts, clean_text, drop_near_duplicates, is_spam
from pipeline.schema import category_for_members, infer_category


def test_clean_text_strips_urls_and_handles():
    cleaned = clean_text("See https://example.com/a and @alice.bsky for the thread")
    assert "http" not in cleaned
    assert "@" not in cleaned
    assert "thread" in cleaned


def test_spam_and_short_posts_are_dropped():
    posts = [
        {"uri": "a", "author": "ann", "text": "A real sentence about housing costs in the city today.", "likes": 3, "created_at": "t"},
        {"uri": "b", "author": "bot", "text": "hi", "likes": 0, "created_at": "t"},
        {"uri": "c", "author": "bot", "text": "aaaaaaaaaaaa look at this amazing offer now", "likes": 0, "created_at": "t"},
        {"uri": "d", "author": "bot", "text": "buy followers buy followers and grow overnight please", "likes": 0, "created_at": "t"},
        {"uri": "e", "author": "bot", "text": "gm", "likes": 2, "created_at": "t"},
        {"uri": "f", "author": "bot", "text": "Follow for follow and check my pinned crypto giveaway today!!!", "likes": 2, "created_at": "t"},
        {"uri": "a", "author": "ann", "text": "A real sentence about housing costs in the city today.", "likes": 9, "created_at": "t"},
    ]
    kept = clean_posts(posts)
    assert [post["uri"] for post in kept] == ["a"]
    assert kept[0]["likes"] == 3
    assert is_spam("hi")
    assert is_spam("Follow for follow please and thanks")


def test_near_duplicates_are_dropped_from_the_live_window():
    posts = [
        {"uri": "a", "clean_text": "The same civic argument posted twice today in this feed."},
        {"uri": "b", "clean_text": "The same civic argument posted twice today in this feed."},
        {"uri": "c", "clean_text": "A different civic argument about wages and hours."},
    ]
    kept = drop_near_duplicates(posts)
    assert [post["uri"] for post in kept] == ["a", "c"]


def test_infer_category_uses_post_text_for_newspaper_sections():
    assert infer_category("Untitled", [], ["Stuck at the 1995 World Series logo reveal tonight."]) == "Sports"
    assert infer_category("Untitled", [], ["Ukraine and NATO talks after the latest Russia strike."]) == "World"
    assert infer_category("Untitled", [], ["ChatGPT and other LLM tools are shipping in the office."]) == "Technology"


def test_majority_section_breaks_ties_to_other():
    members = [
        {"section": "Sports"},
        {"section": "Sports"},
        {"section": "World"},
        {"section": "World"},
    ]
    assert category_for_members("Untitled", [], [], members) == "Other"


def test_majority_section_uses_jev_labels_when_present():
    members = [{"section": "Health"}, {"section": "Health"}, {"section": "Sports"}]
    assert category_for_members("ChatGPT", ["gpt"], ["ignore the keywords"], members) == "Health"
