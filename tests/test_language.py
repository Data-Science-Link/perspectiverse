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


def test_stored_english_posts_with_place_particles_not_language_drops():
    """Exact production texts that wrongly dropped at d49a217 (da/de foreign hits)."""
    assert looks_english(
        "Jon Ossoff is the stone cold lock o' da century ... o' da week."
    )
    assert looks_english(
        "RIO HANA Villa Da Nang — Rooftop Sunset & Private Pool Villa 🏡🌅\n"
        "Twilight rooftop lounge overlooking the Marble Mountains, private billiards room, "
        "courtyard lap pool & cane-detailed suites in Da Nang ✨\n"
        "📸 Photography: Đặng Phong — Hà Phong Visuals\n"
        "🌐 haphong.co"
    )
    assert looks_english(
        "🇪🇸 Spain Official alert: Extreme rain warning Area: Litoral sur de Valencia "
        "Severity: Red Red Rain Warning issued for Spain - Litoral sur de Valencia\n"
        "Source: MeteoAlarm\nWeather Now: App Store / Google Play\n#WeatherNow\n#Spain"
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


def test_reviewer_english_frame_and_normalization_fixtures():
    """bc-269b82cc review: sports bots, Kick mods, strikethrough, PT lottery lines."""
    sports = [
        "GOAL! 55' — Xesc Fullana scores for Poblense. Yeclano 1–2 Poblense. Segunda División RFEF - Group 3",
        "GOAL! 28' — P. Mikita scores for Polonia Środa. Lech Poznań II 1–2 Polonia Środa. III Liga - Group 2",
        "GOAL! 49' — J. Pedraza scores for Sevilla Atletico. Antoniano 1–2 Sevilla Atletico. Segunda División RFEF - Group 4",
        "Anna·Anvegard 11' — Goal for Häcken W (penalty). Häcken W 1–0 Hammarby W. Damallsvenskan",
        "GOAL! 7' — P. Petre scores for FC Bacau. FC Bacau 3–0 Gloria Bistriţa. Liga II",
        "GOAL! 14' — M. Conde scores for Sporting Gijón II (penalty). Sporting Gijón II 3–0 Colunga. Tercera División RFEF - Group 2",
        "GOAL! 9' — R. Marquez scores for Antoniano (penalty). Antoniano 1–0 Sevilla Atletico. Segunda División RFEF - Group 4",
        "GOAL! 10' — A. Ladera scores for Villafranca. Villafranca 1–0 Gévora. Tercera División RFEF - Group 14",
    ]
    for line in sports:
        assert looks_english(line)

    assert looks_english("Just seen a Dutch Mike Neville doppelgänger.")
    assert looks_english(
        "S̶o̶ w̶e̶ s̶h̶o̶u̶l̶d̶ g̶o̶ a̶h̶e̶a̶d̶ w̶i̶t̶h̶ A̶l̶ S̶m̶i̶t̶h̶/J̶a̶k̶e̶ "
        "F̶e̶a̶t̶h̶e̶r̶s̶t̶o̶n̶ t̶o̶x̶i̶c̶ y̶a̶o̶i̶ a̶f̶t̶e̶r̶ a̶l̶l̶?̶"
    )
    assert looks_english(
        "#ac7ionman #kickban\niNachoBaby 🔨 BANNED by Ac7ionMan (after 1s)\n"
        '"S i g n u p o n A n t i s l a v e . c o m F r e e s p e e c h p l a t f o r m"\n'
        "kick.com/ac7ionman"
    )
    assert looks_english(
        "#feef #kicktimeout\nBEURRSG ⏳ 1m timeout by BotRix (after 10m13s)\n"
        '"SHOW B OOBS HaHaa HaHaa SHOW B OOBS HaHaa HaHaa"\n'
        "kick.com/feef"
    )

    assert not looks_english(
        "Geórgia vira polo de barrigas de aluguel para estrangeiros"
    )
    assert not looks_english("Fetiches mais populares no brasil ... acho que não")
    assert not looks_english(
        "O governo do Brasil anunciou novas medidas econômicas hoje"
    )
    assert not looks_english(
        "Resultado da Lotofácil de hoje: veja números e ganhadores do concurso 3806 (sexta, 16/10)"
    )
    assert not looks_english(
        "Resultado da Quina de hoje: veja números e ganhadores do concurso 7144 (sexta, 16/10)"
    )
    assert not looks_english(
        "Veja o resultado da Lotofácil concurso 3803 desta terça-feira (13)"
    )


def test_clean_text_strips_bare_domains_for_clustering():
    raw = "There it is!! bsky.app/profile/mari… still a real story about the bill."
    stripped = clean_text(raw)
    assert "bsky.app" not in stripped
    assert "bill" in stripped
