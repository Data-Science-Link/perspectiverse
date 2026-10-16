"""Planet overlap keeps a label only inside one scope, above the threshold."""

from decimal import Decimal

from pipeline.costs import format_usd, project_measured_daily_usd, reuse_daily_usd
from pipeline.planet_reuse import match_planets, planets_from_payload, share_changed


def _planet(scope: str, name: str, posts: set[tuple[str, str]], post_count: int = 5) -> dict:
    return {"scope": scope, "name": name, "posts": frozenset(posts), "post_count": post_count}


def test_greedy_match_stays_inside_one_scope_and_spends_a_planet_once():
    shared = {("a", "one"), ("a", "two"), ("a", "three")}
    yesterday = [
        _planet("global", "Global story", shared),
        _planet("section:Politics", "Section copy", shared),
        _planet("global", "Other", {("b", "only")}),
    ]
    today = [
        _planet("global", "Today other", {("b", "only"), ("b", "extra")}),
        _planet("global", "Today story", {("a", "one"), ("a", "two")}),
        _planet("section:Politics", "Today section", shared),
    ]
    matches = match_planets(today, yesterday)
    assert matches[0]["name"] == "Other"
    assert matches[0]["score"] == Decimal(1) / Decimal(2)
    assert matches[1]["name"] == "Global story"
    assert matches[1]["score"] == Decimal(2) / Decimal(3)
    assert matches[2]["name"] == "Section copy"
    assert matches[2]["score"] == Decimal(1)
    # The section planet is not a second match for the global post set.
    assert matches[1]["yesterday_index"] != matches[2]["yesterday_index"]


def test_threshold_decides_which_matched_planets_keep_the_label():
    yesterday = [_planet("global", "Old", {("a", "one"), ("a", "two"), ("a", "three"), ("a", "four")})]
    today = [_planet("global", "New", {("a", "one"), ("a", "two"), ("a", "three"), ("a", "five")})]
    matches = match_planets(today, yesterday)
    # 3 shared of 5 distinct representative posts.
    assert matches[0]["score"] == Decimal(3) / Decimal(5)
    at_half = share_changed(matches, Decimal("0.5"))
    at_eighths = share_changed(matches, Decimal("0.8"))
    assert at_half["kept"] == 1 and at_half["changed"] == 0
    assert at_eighths["kept"] == 0 and at_eighths["changed"] == 1
    assert at_eighths["share"] == Decimal(1)


def test_payload_post_set_is_author_and_text_not_a_uri():
    payload = {
        "topics": [
            {
                "name": "Story",
                "post_count": 40,
                "perspectives": [
                    {
                        "representative_posts": [
                            {"author": "ada", "text": "Same words", "likes": 1},
                            {"author": "ada", "text": "Same words", "likes": 2},
                        ]
                    }
                ],
            }
        ],
        "sections": {"Politics": []},
    }
    planets = planets_from_payload(payload)
    assert len(planets) == 1
    assert planets[0]["posts"] == frozenset({("ada", "Same words")})
    assert planets[0]["post_count"] == 40
    assert planets[0]["scope"] == "global"


def test_measured_oct_shares_price_option_1_and_option_1_plus_3_the_same():
    """Counts from the last data-snapshot edition of each day, thresholds 0.5 and 0.8.

    Option 1+3 is the same steady day. Dropping the shortfall does not cut it further.
    """
    projected = project_measured_daily_usd(
        measured_posts=9985,
        jev_usd=Decimal("0.03808182"),
        label_usd=Decimal("0.11712596"),
        jev_calls=1362,
        measured_planets=110,
    )
    jev = projected["steady_jev_usd"]
    label = next(item["label_usd"] for item in projected["assumptions"] if item["id"] == "planets")
    measured = (
        (Decimal("0.5"), 93, 110, Decimal("0.65131248")),
        (Decimal("0.5"), 97, 109, Decimal("0.66551253")),
        (Decimal("0.5"), 88, 110, Decimal("0.63679274")),
        (Decimal("0.8"), 104, 110, Decimal("0.68325593")),
        (Decimal("0.8"), 107, 109, Decimal("0.69481844")),
        (Decimal("0.8"), 107, 110, Decimal("0.69196777")),
    )
    for _threshold, changed, planets, expected in measured:
        priced = reuse_daily_usd(jev, label, changed=changed, planets=planets)
        assert format_usd(priced["option_1_usd"]) == format_usd(expected)
        assert priced["option_1_plus_3_usd"] == priced["option_1_usd"]
        assert priced["option_1_usd"] > Decimal("0.50")
