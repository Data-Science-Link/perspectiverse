"""Local language and link-only filters. No model and no network."""

from pipeline.cleaning import clean_text, has_link_host
from pipeline.language import (
    edition_filter_reason,
    is_link_only,
    looks_english,
    partition_posts,
)


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
    assert not is_link_only("There it is!! bsky.app/profile/mari...")
    assert not is_link_only(
        "You might find this video heartening. youtu.be/SOSOyr1yPao "
        "because the committee finally published the full report today."
    )


def test_reviewer_commentary_with_links_is_kept():
    assert not is_link_only("There it is!! bsky.app/profile/mari/example/post")
    assert not is_link_only(
        "https://news.yahoo.com/foo This is ridiculous!"
    )
    assert not is_link_only(
        "Another gun tragedy www.nytimes.com/2026/10/01/us/example.html"
    )
    assert not is_link_only("Vote Blue! www.cnbc.com/2026/10/01/example.html")
    assert not is_link_only("Oh thank god https://www.reddit.com/r/example/comments/abc")
    assert not is_link_only(
        "Good Evening Colonel youtu.be/oCi0eJ_yntE"
    )
    assert not is_link_only(
        "#netanyahu has to go www.theguardian.com/world/2026/oct/01/example"
    )


def test_gift_link_labels_stay_link_only():
    assert is_link_only("FREE ARTICLE LINK\n\nwww.nytimes.com/2026/10/12/us/example")
    assert is_link_only("Gift link youtu.be/abc123")


def test_portuguese_posts_are_not_english():
    assert not looks_english(
        "Geórgia vira polo de barrigas de aluguel para estrangeiros"
    )
    assert not looks_english(
        "Veja o resultado da Quina concurso 7141 desta terça-feira (13)"
    )
    assert not looks_english(
        "Fetiches mais populares no brasil ... acho que não"
    )
    assert not looks_english(
        "O governo do Brasil anunciou novas medidas econômicas hoje"
    )


def test_english_false_positives_from_portuguese_shortcut_stay():
    assert looks_english(
        "Sherman tank note on the Régiment de Chars de Combat in 1944."
    )
    assert looks_english(
        "Any thoughts on best sherry bodega(s) to visit in El Puerto de Santa María? no idea if it's best."
    )
    assert looks_english(
        "there should be a post-credits scene with no music in Poké Prison, no elaboration needed"
    )
    assert looks_english("Hey DG — Río Rancho. No signs no billboards anywhere.")
    assert looks_english(
        "Jon Ossoff is the stone cold lock o' da century and o' da week for Georgia."
    )


def test_english_with_names_and_loanwords_stays():
    assert looks_english(
        "The committee will meet in São Paulo after the vote on the housing bill."
    )
    assert looks_english(
        "Read the senate bill at https://example.com/story before Friday."
    )


def test_english_with_links_not_link_only():
    assert not is_link_only(
        "No, it's literally not true. https://www.bls.gov/news.release/pdf/empsit.pdf"
    )
    assert not is_link_only(
        "This is really fucked up. https://www.theatlantic.com/politics/archive/2026/01/example/678901/"
    )
    assert not is_link_only(
        "I voted blue in Florida. https://www.tiktok.com/t/ZPLSfPvt7/"
    )
    assert not is_link_only(
        "wow it keeps happening bsky.app/profile/example.bsky.social/post/abc"
    )
    assert not is_link_only(
        "Block them all. https://pluralistic.net/2026/01/01/example/"
    )


def test_handles_and_filenames_are_not_links():
    assert not has_link_host("Menacing Avery for @avery2006.bsky.social")
    assert not has_link_host("@rosszb.bsky.social is your guy.")
    assert not has_link_host("Attached sicko.jpg for the thread")
    assert not has_link_host("We use Node.js in production")
    assert not has_link_host("See README.md for details")
    assert not has_link_host("t2.micro instance pricing")
    assert not has_link_host("Mr.Beast donated again")


def test_english_posts_with_domains_in_review_false_positives():
    assert looks_english(
        "Jev meets the Trolley Problem https://zachlandes.com/trolley-problem/ and more"
    )
    assert looks_english(
        "Actor Jesse Plemons says he'll be voting for Gina Hinojosa in the primary."
    )
    assert looks_english(
        "Hegseth Accused of Exposing Troops' Locations newrepublic.com/article/example-path"
    )
    assert looks_english("Netanyahu's been a liar his whole life.")
    assert looks_english("Give now to help Dan Osborn win this Senate seat in Nebraska.")


def test_edition_filter_uses_raw_text_over_stale_clean_text():
    post = {
        "text": "No, it's literally not true. https://www.bls.gov/news.release/pdf/empsit.pdf",
        "clean_text": "No, it's literally not true.",
    }
    assert edition_filter_reason(post) is None


def test_tambem_counts_as_portuguese():
    assert not looks_english("Isso também é um problema para o governo e para nós")


def test_clean_text_strips_bare_domains_for_clustering():
    raw = "There it is!! bsky.app/profile/mari… still a real story about the bill."
    stripped = clean_text(raw)
    assert "bsky.app" not in stripped
    assert "bill" in stripped
