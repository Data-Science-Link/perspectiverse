"""Login-wall and paywall boilerplate must not reach clustering."""

from pipeline.cleaning import clean_posts, is_login_wall_boilerplate
from pipeline.jev_prefilter import prefilter_reason, DuplicateIndex


def test_boilerplate_wall_posts_are_dropped():
    positives = [
        "Sign in to view this content.",
        "Please log in to continue reading.",
        "Verify you are human before continuing.",
        "Cookies must be enabled to use this site.",
        "Subscribe to read the rest of this article.",
        "Create an account to view this story.",
        "Enable JavaScript to continue.",
        "Attention Required! | Cloudflare",
    ]
    for text in positives:
        assert is_login_wall_boilerplate(text)


def test_real_posts_that_mention_login_are_kept():
    negatives = [
        (
            "Welp,we've gone behind a login wall for the night. Didn't want to. "
            "The AI corps and their scraperbot armies made it impossible to open."
        ),
        "I need three logins to watch one weekend. The product is fragmentation.",
        "Streaming that still needs a cable login is the hangover of the last monopoly.",
        "A district that buys seven dashboards has not bought instruction. It has bought logins.",
        "The site now says sign in to view every article and I think that kills discourse.",
        "Two-factor auth at work is annoying but I still want better account security.",
    ]
    for text in negatives:
        assert not is_login_wall_boilerplate(text)


def test_clean_posts_drops_boilerplate_before_clustering():
    posts = [
        {
            "uri": "at://good",
            "author": "ann",
            "text": "Housing policy should not depend on who you know at city hall.",
            "likes": 1,
            "created_at": "t",
        },
        {
            "uri": "at://wall",
            "author": "web",
            "text": "Sign in to view this post on the forum.",
            "likes": 0,
            "created_at": "t",
        },
    ]
    kept = clean_posts(posts)
    assert [post["uri"] for post in kept] == ["at://good"]


def test_jev_prefilter_marks_boilerplate():
    post = {
        "uri": "at://wall",
        "text": "Log in to continue.",
        "clean_text": "Log in to continue.",
    }
    assert prefilter_reason(post, DuplicateIndex()) == "boilerplate"
