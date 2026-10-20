"""Catch-all clusters are re-split into specific stories (#104)."""

import numpy as np

from pipeline.assemble import topic_name
from pipeline.label import catchall_reasons, label_term_coverage, split_catchall_posts
from pipeline.live import _build_topics
from tests.test_faces_53 import SETTINGS, _blobs


def _posts(specs):
    """specs is (word, text, size). One embedding neighborhood, so faces mix the stories."""
    posts = []
    sizes = []
    for word, text, size in specs:
        sizes.append(size)
        for copy in range(size):
            body = f"{text} {copy}"
            posts.append(
                {
                    "uri": f"at://{word}/{copy}",
                    "author": f"{word}.{copy}",
                    "clean_text": body,
                    "text": body,
                    "likes": copy,
                }
            )
    matrix = _blobs(sizes, seed=4)
    # Pull every group onto one center so the face split cannot see the stories.
    center = matrix[: sizes[0]].mean(axis=0)
    center = center / np.linalg.norm(center)
    rng = np.random.default_rng(4)
    mixed = center + rng.normal(size=(len(posts), matrix.shape[1])) * 0.01
    mixed = mixed / np.linalg.norm(mixed, axis=1, keepdims=True)
    return posts, mixed


def _candidate(posts, matrix, terms):
    return {
        "topics": [
            {
                "id": 0,
                "size": len(posts),
                "member_indices": list(range(len(posts))),
                "terms": terms,
            }
        ],
        "matrix": matrix,
        "assignments": [],
        "noise_count": 0,
    }


def test_label_term_coverage_folds_plurals_and_flags_a_rare_word():
    posts = [{"text": "The company raised prices."} for _ in range(22)]
    posts += [{"text": "A different remark about models."} for _ in range(157)]
    assert label_term_coverage("Companies", posts) == 22 / 179
    assert label_term_coverage("Companies", posts) < 0.30
    think = [{"text": "I think this is the issue."} for _ in range(23)]
    think += [{"text": "A model wrote the paper."} for _ in range(133)]
    assert abs(label_term_coverage("Think", think) - 23 / 156) < 1e-9


def test_catchall_reasons_match_the_three_signals():
    diesel = [
        {"title": "Diesel Stockpile", "summary": "Reserves.", "representative_posts": [{"text": "diesel stockpile refinery"}]},
        {"title": "Diesel Price", "summary": "The price.", "representative_posts": [{"text": "diesel price stockpile"}]},
    ]
    courts = [
        {"title": "Border Ruling", "summary": "A case.", "representative_posts": [{"text": "border asylum ruling"}]},
        {"title": "Campaign Ad", "summary": "An ad.", "representative_posts": [{"text": "campaign rally advertisement"}]},
    ]
    posts = [{"text": "diesel stockpile"} for _ in range(10)]
    assert catchall_reasons(diesel, posts, "Diesel Stockpile") == []
    split_reasons = catchall_reasons(courts, posts, "Courts")
    assert "more than one story" in split_reasons
    assert "no shared claim" in split_reasons
    rare = [{"text": "company filing"} for _ in range(2)] + [{"text": "model paper"} for _ in range(8)]
    assert catchall_reasons(diesel, rare, "Companies") == ["label term in under 30% of posts"]


def test_coherence_check_still_flags_a_catchall_before_the_split():
    """Companies and Think still fail the check before any re-split runs.

    A quiet cluster does not. The split is gated on this check, so a run
    that reports zero coherence-blocked planets has not turned the guard off.
    """
    from pipeline.live import _return_catchall_split

    companies = [{"text": "The company raised prices.", "clean_text": "The company raised prices."}] * 22
    companies += [{"text": "A model wrote the paper.", "clean_text": "A model wrote the paper."}] * 157
    reasons = catchall_reasons([], companies, "Companies")
    assert reasons == ["label term in under 30% of posts"]
    assert label_term_coverage("Companies", companies) < 0.30
    think = [{"text": "I think this is the issue.", "clean_text": "I think this is the issue."}] * 23
    think += [{"text": "A model wrote the paper.", "clean_text": "A model wrote the paper."}] * 133
    assert "label term in under 30% of posts" in catchall_reasons([], think, "Think")
    diesel = [{"text": "diesel stockpile refinery price", "clean_text": "diesel stockpile refinery price"}] * 24
    assert catchall_reasons([], diesel, "Diesel Stockpile") == []
    # No reasons means the old drop path. The split function is not called.
    assert (
        _return_catchall_split(
            [],
            {},
            {"terms": ["diesel"]},
            {"section": "All topics"},
            diesel,
            [],
            [],
            0,
        )
        is None
    )


def test_companies_blob_is_split_only_after_the_check_flags_it(capsys):
    """The published log quotes the check, then splits. The blob is not kept whole."""
    posts, matrix = _posts(
        [
            ("psychosis", "ai psychosis psychosis delusion delusion", 16),
            ("factory", "ai factory factory semiconductor semiconductor", 16),
            ("conference", "ai conference conference academic academic", 16),
            ("copyright", "ai copyright copyright artist artist", 16),
        ]
    )
    reasons = catchall_reasons([], posts, "Companies")
    assert reasons
    topics, _membership, _faces = _build_topics(
        posts, _candidate(posts, matrix, ["companies"]), SETTINGS, keep=10
    )
    logged = capsys.readouterr().out
    assert "Splitting Companies: catch-all" in logged
    assert "label term in under 30% of posts" in logged
    assert len(topics) > 1


def test_thin_generic_ai_fragments_merge_and_a_specific_story_stays():
    """Generic 5-post AI scraps are held. Copyright and book stay specific."""
    from pipeline.label import _fragment_stem

    posts = []
    for word in ("concern", "problem", "danger", "right"):
        for copy in range(5):
            text = f"ai {word} {word} {copy}"
            posts.append({"text": text, "clean_text": text})
    for word, extra in (("copyright", "statute"), ("book", "binding")):
        for copy in range(5):
            text = f"ai {word} {word} {extra} {extra} {copy}"
            posts.append({"text": text, "clean_text": text})
    notes: list[str] = []
    buckets = split_catchall_posts(posts, floor=5, notes=notes)
    assert sorted(len(bucket) for bucket in buckets) == [5, 5]
    assert any("thin fragments" in note for note in notes)
    lone = [{"text": f"ai concern concern {copy}", "clean_text": f"ai concern concern {copy}"} for copy in range(5)]
    assert split_catchall_posts(lone, floor=5) == []
    assert _fragment_stem("already") and _fragment_stem("full") and _fragment_stem("first")
    assert not _fragment_stem("book") and not _fragment_stem("copyright")


def test_unsplit_story_is_kept_instead_of_coherence_blocked(capsys):
    """A named story at the planet floor is published when the re-split finds nothing."""
    words = ["alphaaa", "bravooo", "charlii", "deltaaa", "echoooo", "foxtrot", "golfiii", "hotelll"]
    specs = [(word, f"{word} unique{word}", 1) for word in words]
    posts, matrix = _posts(specs)
    topics, membership, _faces = _build_topics(
        posts, _candidate(posts, matrix, ["companies"]), SETTINGS, keep=10
    )
    logged = capsys.readouterr().out
    assert "story stays" in logged
    assert "Coherence blocked" not in logged
    assert len(topics) == 1
    assert topics[0]["post_count"] == 8
    assert len(membership) == 8


def test_split_catchall_posts_separates_ai_stories_and_ignores_glue():
    posts = []
    for word in ("psychosis", "factory", "conference", "copyright"):
        for copy in range(16):
            posts.append({"text": f"ai {word} {word} {word} detail{word} {copy}", "clean_text": f"ai {word} {word} detail{word}"})
    buckets = split_catchall_posts(posts, floor=5)
    assert len(buckets) == 4
    assert sorted(len(bucket) for bucket in buckets) == [16, 16, 16, 16]
    # A word in every post is glue, not a fourth story.
    glued = [{"text": "diesel diesel stockpile refinery"} for _ in range(20)]
    assert split_catchall_posts(glued, floor=5) == []


def test_ai_catchall_becomes_specific_planets_instead_of_a_drop(capsys):
    """Companies/Think shape: one ball, no word in 30% of posts, several real stories."""
    posts, matrix = _posts(
        [
            ("psychosis", "ai psychosis psychosis delusion delusion", 16),
            ("factory", "ai factory factory semiconductor semiconductor", 16),
            ("conference", "ai conference conference academic academic", 16),
            ("copyright", "ai copyright copyright artist artist", 16),
        ]
    )
    topics, membership, _faces = _build_topics(
        posts, _candidate(posts, matrix, ["conference"]), SETTINGS, keep=10
    )
    logged = capsys.readouterr().out
    assert "catch-all" in logged
    assert "no face kept a shared claim" not in logged
    assert len(topics) == 4
    names = " ".join(topic["name"].lower() for topic in topics)
    for word in ("psychosis", "factory", "conference", "copyright"):
        assert word in names
    authors = {uri.split("/")[2] for uri, _topic in membership}
    assert authors == {"psychosis", "factory", "conference", "copyright"}


def test_tiny_catchall_children_do_not_crowd_out_a_later_planet(capsys):
    """A 5-post AI scrap must not take a global slot ahead of a later real story."""
    small, small_matrix = _posts(
        [
            ("psychosis", "ai psychosis psychosis delusion delusion", 5),
            ("factory", "ai factory factory semiconductor semiconductor", 5),
            ("conference", "ai conference conference academic academic", 5),
            ("copyright", "ai copyright copyright artist artist", 5),
        ]
    )
    large, large_matrix = _posts(
        [("corruption", "trump corruption corruption bribery scandal", 24)]
    )
    posts = small + large
    clustered = {
        "topics": [
            {
                "id": 0,
                "size": len(small),
                "member_indices": list(range(len(small))),
                "terms": ["conference"],
            },
            {
                "id": 1,
                "size": len(large),
                "member_indices": list(range(len(small), len(posts))),
                "terms": ["corruption"],
            },
        ],
        "matrix": np.vstack([small_matrix, large_matrix]),
        "assignments": [],
        "noise_count": 0,
    }
    topics, _membership, _faces = _build_topics(posts, clustered, SETTINGS, keep=2)
    names = " ".join(str(topic.get("name") or "").lower() for topic in topics)
    assert "corruption" in names
    assert len(topics) <= 2
    del capsys


def test_merged_thin_fragments_do_not_jump_the_global_queue(capsys):
    """Held generic scraps do not take the global slot a later real story needs."""
    small, small_matrix = _posts(
        [
            ("concern", "ai concern concern", 5),
            ("problem", "ai problem problem", 5),
            ("danger", "ai danger danger", 5),
            ("right", "ai right right", 5),
            ("copyright", "ai copyright copyright statute statute", 5),
        ]
    )
    large, large_matrix = _posts(
        [("corruption", "trump corruption corruption bribery scandal", 24)]
    )
    posts = small + large
    clustered = {
        "topics": [
            {
                "id": 0,
                "size": len(small),
                "member_indices": list(range(len(small))),
                "terms": ["conference"],
            },
            {
                "id": 1,
                "size": len(large),
                "member_indices": list(range(len(small), len(posts))),
                "terms": ["corruption"],
            },
        ],
        "matrix": np.vstack([small_matrix, large_matrix]),
        "assignments": [],
        "noise_count": 0,
    }
    topics, _membership, _faces = _build_topics(posts, clustered, SETTINGS, keep=1)
    names = " ".join(str(topic.get("name") or "").lower() for topic in topics)
    assert topics and "corruption" in names
    assert len(topics) == 1
    del capsys


def test_coherent_politics_story_stays_one_planet(capsys):
    """Trump Corruption shape: the label word is the subject, so it is not re-split."""
    posts, matrix = _posts(
        [("corruption", "trump corruption corruption bribery scandal", 24)]
    )
    topics, _membership, _faces = _build_topics(
        posts, _candidate(posts, matrix, ["corruption"]), SETTINGS, keep=10
    )
    logged = capsys.readouterr().out
    assert len(topics) == 1
    assert "corruption" in topics[0]["name"].lower()
    assert "catch-all" not in logged
    assert "Coherence blocked" not in logged


def test_ice_abuse_and_voter_probe_split(capsys):
    """#135: abuse accountability and a voter-roll probe are two stories."""
    abuse, abuse_matrix = _story("abuse", "ice abuse accountability beating agent", 20, seed=3)
    voter, voter_matrix = _story("voter", "voter records registration probe", 16, seed=9)
    posts = abuse + voter
    matrix = np.vstack([abuse_matrix, voter_matrix])
    topics, membership, _faces = _build_topics(
        posts, _candidate(posts, matrix, ["glued"]), SETTINGS, keep=10
    )
    logged = capsys.readouterr().out
    assert "Splitting" in logged
    assert len(topics) == 2
    names = _planet_blob(topics)
    assert "abuse" in names
    assert "voter" in names or "probe" in names or "records" in names
    authors = {uri.split("/")[2] for uri, _topic in membership}
    assert authors == {"abuse", "voter"}
    del capsys


def test_trans_rights_and_site_security_split(capsys):
    """#133: a login-wall face is not a perspective on trans rights."""
    trans, trans_matrix = _story("trans", "trans rights healthcare erasure", 20, seed=5)
    login, login_matrix = _story("login", "login security password account", 12, seed=8)
    posts = trans + login
    matrix = np.vstack([trans_matrix, login_matrix])
    topics, _membership, _faces = _build_topics(
        posts, _candidate(posts, matrix, ["glued"]), SETTINGS, keep=10
    )
    logged = capsys.readouterr().out
    assert "Splitting" in logged
    assert len(topics) == 2
    names = _planet_blob(topics)
    assert "trans" in names or "erasure" in names or "healthcare" in names
    assert "login" in names or "security" in names or "password" in names
    del capsys


def _story(word, text, size, seed):
    matrix = _blobs([size], seed=seed)
    posts = []
    for copy in range(size):
        body = f"{text} {text} {copy}"
        posts.append(
            {
                "uri": f"at://{word}/{copy}",
                "author": f"{word}.{copy}",
                "clean_text": body,
                "text": body,
                "likes": copy,
            }
        )
    return posts, matrix


def _planet_blob(topics) -> str:
    parts = []
    for topic in topics:
        parts.append(str(topic.get("name") or ""))
        for face in topic.get("perspectives") or []:
            parts.append(str(face.get("title") or ""))
            parts.extend(face.get("top_terms") or [])
    return " ".join(parts).lower()


def test_topic_name_is_the_label_the_coverage_test_sees():
    assert topic_name(["conference"]) == "Conference"
