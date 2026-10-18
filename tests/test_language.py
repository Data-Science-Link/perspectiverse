"""Local language and link-only filters. No model and no network."""

from pipeline.cleaning import clean_text
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


def test_bare_youtube_and_bsky_links_are_link_only():
    assert is_link_only("youtu.be/pY0A8RxdBlg")
    assert is_link_only("#ValhallaVFT youtu.be/Gil2wVgY04U?...")
    assert is_link_only("There it is!! bsky.app/profile/mari...")
    assert not is_link_only(
        "You might find this video heartening. youtu.be/SOSOyr1yPao "
        "because the committee finally published the full report today."
    )


def test_portuguese_posts_are_not_english():
    assert not looks_english(
        "Geórgia vira polo de barrigas de aluguel para estrangeiros"
    )
    assert not looks_english(
        "Veja o resultado da Quina concurso 7141 desta terça-feira (13)"
    )


def test_english_with_names_and_loanwords_stays():
    assert looks_english(
        "The committee will meet in São Paulo after the vote on the housing bill."
    )
    assert looks_english(
        "Read the senate bill at https://example.com/story before Friday."
    )


def test_clean_text_strips_bare_domains_for_clustering():
    raw = "There it is!! bsky.app/profile/mari… still a real story about the bill."
    stripped = clean_text(raw)
    assert "bsky.app" not in stripped
    assert "bill" in stripped
