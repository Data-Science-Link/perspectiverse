"""Local language and link-only filters. No model and no network."""

from pipeline.language import is_link_only, looks_english, partition_posts


def test_dutch_cyrillic_and_link_only_drop_and_english_stays():
    posts = [
        {"clean_text": "The senate should vote on the bill before Friday."},
        {"clean_text": "Het is niet een goed plan want de regering heeft geen meerderheid."},
        {"clean_text": "https://example.com/story"},
        {"clean_text": "Yes please"},
        {"text": "Привет это не английский текст для проверки фильтра"},
        {"clean_text": "Read the senate bill at https://example.com/story before Friday."},
    ]
    kept, language, links = partition_posts(posts)
    assert links == 1
    assert language == 2
    assert [post.get("clean_text") or post.get("text") for post in kept] == [
        posts[0]["clean_text"],
        posts[3]["clean_text"],
        posts[5]["clean_text"],
    ]


def test_one_foreign_word_does_not_drop_english():
    assert looks_english("The committee will meet after the vote, niet the hearing.")
    assert not is_link_only("The committee posted the bill at https://example.com/bill today.")
    assert is_link_only("https://example.com/only")
