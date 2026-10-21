import json
import threading
import time

import pytest

from pipeline.label import (
    FALLBACK_TITLE,
    LABEL_READ_TIMEOUT_DEFAULT,
    LABEL_READ_TIMEOUT_MAX,
    LABEL_READ_TIMEOUT_MIN,
    TIMEOUT_CIRCUIT_LIMIT,
    LabelBudgetExceeded,
    build_perspective_prompt,
    build_planet_name_prompt,
    build_prompt,
    build_topic_prompt,
    classify_label_error,
    compute_read_timeout,
    configured_label_read_timeout_max,
    dead_provider_worst_case,
    format_label_latency_summary,
    format_latency_histogram,
    label_perspective,
    label_read_timeout,
    label_topic,
    parse_label,
    record_label_latency,
    reset_label_latency_samples,
    reset_label_timeout_circuit,
    resolve_openai_base_url,
    resolve_openai_model,
    retry_budget_seconds,
    set_label_deadline,
    timeout_circuit_is_open,
    _openai_generate,
    _retry_fits_budget,
)


@pytest.fixture(autouse=True)
def _reset_label_runtime():
    reset_label_latency_samples()
    reset_label_timeout_circuit()
    set_label_deadline(None)
    yield
    reset_label_latency_samples()
    reset_label_timeout_circuit()
    set_label_deadline(None)
from pipeline.settings import MAX_PROMPT_POSTS


def _prompt_post_count(prompt: str) -> int:
    body = prompt.split("Posts:\n", 1)[1]
    return len([line for line in body.splitlines() if line.startswith("- ")])


def test_label_prompts_are_bounded_on_a_100k_planet():
    """Face, name, and topic prompts stay at the 40-post ceiling on a huge planet."""
    posts = [
        {"text": f"claim {index} about the bill " + ("word " * 20), "likes": index % 7, "author": "a"}
        for index in range(100_000)
    ]
    assert _prompt_post_count(build_perspective_prompt(posts, post_limit=100_000)) == MAX_PROMPT_POSTS
    assert _prompt_post_count(build_perspective_prompt(posts, post_limit=12)) == 12
    assert _prompt_post_count(build_perspective_prompt(posts)) == MAX_PROMPT_POSTS
    assert _prompt_post_count(build_planet_name_prompt(posts, [{"title": "Bill", "summary": "A bill."}], post_limit=100_000)) == MAX_PROMPT_POSTS
    assert _prompt_post_count(build_topic_prompt(posts, ["bill"], post_limit=100_000)) == MAX_PROMPT_POSTS
    assert "claim 99999" not in build_perspective_prompt(posts, post_limit=100_000)


def test_prompt_demands_json_only():
    prompt = build_prompt([{"text": "Rent is due.", "likes": 3}])
    assert '{"title"' in prompt
    assert "JSON only" in prompt
    assert "arguments" in prompt
    assert "paraphrase" in prompt
    assert "Anti Republican" in prompt
    assert "insult" in prompt.lower()


def test_weak_term_does_not_become_the_face_title():
    posts = [
        {"text": "AI evangelists are morally unequipped to oversee this technology.", "likes": 9},
        {"text": "Those AI evangelists keep shipping it without consent.", "likes": 4},
    ]
    calls = {"n": 0}

    def generate(prompt):
        calls["n"] += 1
        if "not publishable" in prompt:
            return json.dumps(
                {
                    "title": "Unfit Evangelists",
                    "summary": "The posts say AI evangelists are morally unequipped to govern the technology.",
                    "arguments": [
                        "AI evangelists are morally unequipped to oversee this technology.",
                        "Those AI evangelists keep shipping it without consent.",
                    ],
                }
            )
        return json.dumps(
            {
                "title": "AI Criticism",
                "summary": "These posts share various concerns about the tools.",
                "arguments": [
                    "AI evangelists are morally unequipped to oversee this technology.",
                    "Those AI evangelists keep shipping it without consent.",
                ],
            }
        )

    labeled = label_perspective(posts, ["most"], generate=generate)
    assert calls["n"] >= 2
    assert labeled["title"] not in {"Most", "AI Criticism", "Mixed remarks"}
    assert "evangelist" in labeled["title"].lower()
    assert "various concerns" not in labeled["summary"].lower()
    assert "evangelists" in labeled["summary"].lower()


def test_a_shared_commodity_counts_as_one_subject():
    from pipeline.label import specific_shared_words

    diesel = [
        {
            "title": "Diesel Export",
            "representative_posts": [{"text": "The president will not ban diesel exports this week."}],
        },
        {
            "title": "Oil Release",
            "representative_posts": [{"text": "Allies will release diesel from emergency stockpiles."}],
        },
    ]
    courts = [
        {
            "title": "Judicial Compliance",
            "representative_posts": [{"text": "Nothing happens when officials defy a judge's order."}],
        },
        {
            "title": "No Prosecution",
            "representative_posts": [{"text": "The department will not reopen the renovation investigation."}],
        },
    ]
    assert "diesel" in specific_shared_words(diesel)
    assert specific_shared_words(courts) == set()
    cornell = [
        {
            "title": "Rape Culture",
            "representative_posts": [{"text": "Trump sympathizes with the rapists at that college."}],
        },
        {
            "title": "Cornell Rape Case",
            "representative_posts": [{"text": "The Cornell rape suspects were students at that college."}],
        },
    ]
    politicians = [
        {
            "title": "Female Candidate",
            "representative_posts": [{"text": "AOC will move the field and Angie Nixon belongs in America."}],
        },
        {
            "title": "Susan Collins",
            "representative_posts": [{"text": "Susan Collins was caught taking bribes with no consequences."}],
        },
    ]
    assert specific_shared_words(cornell)
    assert specific_shared_words(politicians) == set()
    once = [
        {
            "title": "Outrage Over Issues",
            "summary": "Online discussions prioritize outrage over serious issues.",
            "representative_posts": [
                {"text": "Social media posts spark outrage about discrimination and debate."},
                {"text": "People are furious about a trans man in the Odyssey and the casting."},
                {"text": "The grooming meme treats misconduct allegations like a fandom war."},
            ],
        },
        {
            "title": "Hate Groups",
            "summary": "Hate groups are promoting misogyny.",
            "representative_posts": [
                {"text": "Elliot Rodger fans are evil violent misogynists."},
                {"text": "The incel movement is alive and well among these accounts."},
                {"text": "This trend is misogyny invented by incels and aimed at trans people."},
            ],
        },
    ]
    repeated = [
        {
            "title": "Rape Culture",
            "summary": "Rapists are being sympathized with.",
            "representative_posts": [
                {"text": "Any college fostering rape culture needs to be dismantled."},
                {"text": "The rape apologists are out in full force today."},
                {"text": "Too many people still sympathize with rapists."},
            ],
        },
        {
            "title": "Cornell Rape Case",
            "summary": "Trump supports Cornell rape suspects.",
            "representative_posts": [
                {"text": "Trump was asked about the Cornell rape case and dodged it."},
                {"text": "Trump said he feels badly for the Cornell rape suspects."},
                {"text": "The adjudicated rapist president supports the Cornell rape suspects."},
            ],
        },
    ]
    titled = [
        {
            "title": "Trans Rights",
            "summary": "Trans people should keep their rights.",
            "representative_posts": [
                {"text": "Trans rights are not up for debate in this election."},
                {"text": "Hospitals should provide care without political interference."},
                {"text": "The bill restricts medical treatment for minors."},
            ],
        },
        {
            "title": "Trans Advantage",
            "summary": "Some sports see a trans advantage.",
            "representative_posts": [
                {"text": "A trans athlete should not compete in the women's category."},
                {"text": "Fairness in sport matters more than inclusion here."},
                {"text": "The league changed its eligibility rules last season."},
            ],
        },
    ]
    assert specific_shared_words(once) == set()
    assert specific_shared_words(repeated)
    assert specific_shared_words(titled)
    courts = [
        {
            "representative_posts": [
                {"text": "Judge blocks border wall construction in Big Bend."},
                {"text": "The Justice Department will not prosecute Jerome Powell."},
                {"text": "The criminal investigation into Powell remains closed."},
            ],
        },
        {
            "representative_posts": [
                {"text": "The race for attorney general is about who will fight for you."},
                {"text": "A prosecutor is somebody doing their legal job."},
                {"text": "Congress can't appoint a special prosecutor or counsel."},
            ],
        },
    ]
    assert specific_shared_words(courts) == set()


def test_story_groups_split_faces_that_share_no_subject_word():
    from pipeline.label import story_groups

    diesel = [
        {
            "title": "Diesel Export",
            "representative_posts": [{"text": "The president will not ban diesel exports this week."}],
        },
        {
            "title": "Oil Release",
            "representative_posts": [{"text": "Allies will release diesel from emergency stockpiles."}],
        },
    ]
    courts = [
        {
            "title": "Judicial Compliance",
            "representative_posts": [{"text": "Nothing happens when officials defy a judge's order."}],
        },
        {
            "title": "No Prosecution",
            "representative_posts": [{"text": "The department will not reopen the renovation investigation."}],
        },
    ]
    assert story_groups(diesel) == [[0, 1]]
    assert story_groups(courts) == [[0], [1]]
    glued = courts + diesel
    groups = story_groups(glued)
    assert sorted(tuple(sorted(group)) for group in groups) == [(0,), (1,), (2, 3)]


def test_faces_that_share_no_subject_word_are_different_stories():
    from pipeline.label import faces_share_vocabulary

    judicial = {
        "title": "Judicial Compliance",
        "summary": "Judges' orders are being ignored.",
        "representative_posts": [
            {"text": "Nothing happens when officials defy a judge's order and skip the hearing."}
        ],
    }
    powell = {
        "title": "No Prosecution",
        "summary": "The department will not charge the former chair.",
        "representative_posts": [
            {"text": "The Justice Department will not reopen the Powell renovation investigation."}
        ],
    }
    death = {
        "title": "Death Penalty",
        "summary": "The execution of Christa Pike was torture.",
        "representative_posts": [{"text": "Christa Pike survived a botched execution in Tennessee."}],
    }
    needle = {
        "title": "Lethal Injection",
        "summary": "Lethal injection made Christa Pike suffer.",
        "representative_posts": [{"text": "Christa Pike suffered during the botched execution."}],
    }
    assert faces_share_vocabulary([judicial, powell]) is False
    assert faces_share_vocabulary([death, needle]) is True


def test_different_stories_are_not_one_subject():
    from pipeline.label import perspectives_share_subject

    faces = [
        {"title": "Pentagon Religion", "summary": "The defense secretary opened a religious affairs office."},
        {"title": "Church Alliance", "summary": "A church is partnering with artists on outreach."},
    ]
    assert perspectives_share_subject(faces, backend="heuristic") is True
    assert (
        perspectives_share_subject(
            faces,
            backend="openai",
            generate=lambda _prompt: '{"same": false}',
        )
        is False
    )
    assert (
        perspectives_share_subject(
            faces,
            backend="openai",
            generate=lambda _prompt: "not json",
        )
        is True
    )


def test_camp_title_is_replaced_with_the_claim_terms():
    posts = [{"text": "The rent increase on my block is the whole story tonight.", "likes": 4}]
    labeled = label_perspective(
        posts,
        ["rent", "increase"],
        generate=lambda _prompt: json.dumps(
            {
                "title": "Anti Landlord",
                "summary": "The rent increase on the block is the story.",
                "arguments": [
                    "The rent increase on the block is the whole story.",
                    "The rent increase tonight is what the block is talking about.",
                ],
            }
        ),
    )
    assert labeled["title"] == "Rent Increase"
    assert "Astra" not in labeled["summary"]


def test_invented_entity_is_dropped_and_a_paraphrase_is_kept():
    posts = [{"text": "The rent increase on my block is the whole story tonight.", "likes": 4}]
    labeled = label_perspective(
        posts,
        ["rent"],
        generate=lambda _prompt: json.dumps(
            {
                "title": "Rent Burden",
                "summary": "People are talking about the rent increase.",
                "arguments": [
                    "The rent increase on the block is the whole story.",
                    "OpenAI cancelled GPT-6.1 Astra yesterday.",
                ],
            }
        ),
    )
    arguments = labeled.get("arguments") or []
    assert arguments
    assert all("Astra" not in item and "OpenAI" not in item and "6.1" not in item for item in arguments)
    assert "rent increase" in arguments[0]


def test_duplicate_titles_get_a_suffix():
    from pipeline.label import unique_label

    seen: set[str] = set()
    assert unique_label("Anti Trump", seen) == "Anti Trump"
    assert unique_label("Anti Trump", seen) == "Anti Trump 2"


def test_titles_alike_catches_a_numbered_copy_and_not_a_different_claim():
    from pipeline.label import titles_alike

    assert titles_alike("Pro Ukraine", "Pro Ukraine 2")
    assert titles_alike("AI Criticism", "AI Critique")
    assert titles_alike("Ukraine War", "Ukraine War Updates")
    assert not titles_alike("Pro Ukraine", "Oil Crisis")
    assert not titles_alike("Iran War", "Iran Conflict")
    assert not titles_alike("Death Penalty", "Lethal Injection")


def test_heuristic_summary_uses_a_shown_sentence():
    from pipeline.label import heuristic_label

    labeled = heuristic_label(
        ["rent"],
        [{"text": "Half my paycheck is rent and the lease still went up.", "likes": 4}],
    )
    assert "paycheck" in labeled["summary"]
    assert "concentrate on" not in labeled["summary"]


def test_parse_label_accepts_wrapped_json():
    parsed = parse_label('Sure thing {"title": "Rent Burden", "summary": "People cannot pay rent."}')
    assert parsed["title"] == "Rent Burden"


def test_parse_label_accepts_unescaped_quotes_inside_strings():
    raw = (
        '{"title": "AI Terminology", "summary": "Prefer the term "machine learning" over "AI" here", '
        '"arguments": ["Using "AI" chases funding.", "The narrower name is more accurate."]}'
    )
    parsed = parse_label(raw)
    assert parsed is not None
    assert parsed["title"] == "AI Terminology"
    assert "machine learning" in parsed["summary"]
    assert parsed["arguments"][0].startswith("Using")


def test_parse_label_keeps_arguments_and_topic_name():
    parsed = parse_label(
        '{"name": "AI Jobs", "title": "AI Jobs", "summary": "People argue about automation.", '
        '"arguments": ["Payroll is already changing.", "The threat is quiet."]}'
    )
    assert parsed["name"] == "AI Jobs"
    assert parsed["arguments"][0].startswith("Payroll")


def test_label_topic_without_llm_is_heuristic(monkeypatch):
    monkeypatch.setattr("pipeline.label.ollama_reachable", lambda timeout=0.4: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    labeled = label_topic(
        [{"text": "The model release is eating junior writing jobs this quarter.", "likes": 12}],
        ["model", "jobs"],
        backend="auto",
    )
    assert labeled["name"] == "Model Jobs"
    assert labeled["label_source"] == "heuristic"


def test_invalid_model_output_retries_then_falls_back():
    calls = {"n": 0}

    def generate(_prompt):
        calls["n"] += 1
        return "not json at all"

    labeled = label_perspective(
        [{"text": "Rent is due again.", "likes": 2}],
        ["rent", "housing"],
        generate=generate,
    )
    assert calls["n"] == 2
    assert labeled["title"] == FALLBACK_TITLE
    assert "rent" in labeled["summary"]


def test_second_try_can_succeed():
    calls = {"n": 0}

    def generate(_prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return "nope"
        return json.dumps({"title": "Wage Floor", "summary": "People want a higher wage."})

    labeled = label_perspective([{"text": "Raise the wage.", "likes": 8}], ["wage"], generate=generate)
    assert calls["n"] == 2
    assert labeled["title"] == "Wage Floor"
    assert labeled["label_source"] == "model"


def test_auto_without_llm_uses_heuristic_names(monkeypatch):
    monkeypatch.setattr("pipeline.label.ollama_reachable", lambda timeout=0.4: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    labeled = label_perspective(
        [{"text": "A longer post about housing costs this week in the city.", "likes": 1}],
        ["housing"],
        backend="auto",
    )
    assert labeled["title"] == "Housing"
    assert labeled["label_source"] == "heuristic"
    assert len(labeled["arguments"]) >= 2


def test_empty_openai_base_url_defaults_to_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert resolve_openai_base_url() == "https://api.openai.com/v1"
    assert resolve_openai_model() == "gpt-4o-mini"


def test_deepinfra_base_url_picks_llama_default(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepinfra.com/v1/openai")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert resolve_openai_model() == "meta-llama/Llama-3.3-70B-Instruct-Turbo"


def test_mocked_openai_generate_posts_to_deepinfra(monkeypatch):
    seen = {}

    def fake_read_json(url, *, timeout, data=None, headers=None):
        seen["url"] = url
        seen["authorization"] = (headers or {}).get("Authorization", "")
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"title": "Rent Burden", "summary": "People cannot pay rent."}
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepinfra.com/v1/openai")
    monkeypatch.setenv("OPENAI_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    raw = _openai_generate("hello", resolve_openai_model())
    assert "Rent Burden" in raw
    assert seen["url"] == "https://api.deepinfra.com/v1/openai/chat/completions"
    assert seen["authorization"] == "Bearer test-not-a-real-key"
    from pipeline.http_json import _allowed

    assert _allowed(seen["url"])



def test_openai_generate_backs_off_on_rate_limit(monkeypatch):
    """Concurrent labeling (#53) must not turn a 429 into a dropped face."""
    calls = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(url)
        if len(calls) < 3:
            raise RuntimeError("HTTP 429 from api.deepinfra.com")
        return {"choices": [{"message": {"content": "{\"title\": \"Rent Burden\"}"}}]}

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    assert "Rent Burden" in _openai_generate("hello", "model")
    assert len(calls) == 3


def test_openai_generate_stops_after_bounded_retries(monkeypatch):
    """A 5xx is retried with backoff, and the retries stop."""
    calls = []
    slept = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(url)
        raise RuntimeError("HTTP 503 from api.deepinfra.com")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    with pytest.raises(RuntimeError, match="HTTP 503"):
        _openai_generate("hello", "model")
    assert len(calls) == 3
    assert slept == [2.0, 6.0]


def test_openai_generate_retries_timeouts_with_bounded_backoff(monkeypatch):
    """A timeout is retried with backoff until the cap (four retries after the first read)."""
    calls = []
    slept = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(timeout)
        raise RuntimeError("Request failed for api.deepinfra.com: The read operation timed out")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    reset_label_latency_samples()
    set_label_deadline(None)
    with pytest.raises(RuntimeError, match="timed out"):
        _openai_generate("hello", "model")
    assert calls == [LABEL_READ_TIMEOUT_DEFAULT] * 5
    assert slept == [2.0, 4.0, 8.0, 16.0]


def test_compute_read_timeout_uses_p95_and_clamps():
    assert compute_read_timeout([8.0] * 7) == LABEL_READ_TIMEOUT_DEFAULT
    # p95 is 20s -> 20 * 1.5 + 5 = 35
    assert compute_read_timeout([20.0] * 10) == 35.0
    assert compute_read_timeout([100.0] * 10) == LABEL_READ_TIMEOUT_MAX
    assert compute_read_timeout([1.0] * 10) == LABEL_READ_TIMEOUT_MIN


def test_retry_budget_seconds_counts_a_full_read_for_every_attempt():
    """A 429 retry still performs a read that can block for the whole timeout."""
    assert retry_budget_seconds(0.0, "timeout", read_timeout=40.0) == 40.0
    assert retry_budget_seconds(2.0, "429", read_timeout=40.0) == 42.0
    assert retry_budget_seconds(2.0, "timeout", read_timeout=40.0) == 42.0


def test_retry_fits_budget_uses_shorter_read_timeout():
    reset_label_latency_samples()
    needed = retry_budget_seconds(2.0, "timeout", read_timeout=LABEL_READ_TIMEOUT_DEFAULT)
    set_label_deadline(time.monotonic() + needed - 0.5)
    try:
        fits, reason = _retry_fits_budget(2.0, "timeout")
        assert not fits
        assert f"{needed:.1f}" in reason
        set_label_deadline(time.monotonic() + needed + 1.0)
        fits, _reason = _retry_fits_budget(2.0, "timeout")
        assert fits
    finally:
        set_label_deadline(None)


def test_label_latency_summary_after_successes(monkeypatch):
    clock = {"now": 1_000.0}

    def fake_read_json(url, *, timeout, data=None, headers=None):
        clock["now"] += 10.0
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.monotonic", lambda: clock["now"])
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    for _ in range(3):
        _openai_generate("hello", "model")
    line = format_label_latency_summary()
    assert line is not None
    assert "n=3" in line
    assert "p50=10.0s" in line
    assert "histogram <30s=3, 30-45s=0, 45-90s=0, >90s=0" in line
    assert f"read_timeout={LABEL_READ_TIMEOUT_DEFAULT:.0f}s" in line


def test_openai_generate_records_success_latency_including_the_45_90_bucket(monkeypatch):
    """``_openai_generate`` itself records the sample. The histogram keeps 45–90s."""
    clock = {"now": 0.0}
    delays = iter((60.0, 12.0))

    def fake_read_json(url, *, timeout, data=None, headers=None):
        clock["now"] += next(delays)
        return {"choices": [{"message": {"content": "{\"title\": \"Rent Burden\"}"}}]}

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.monotonic", lambda: clock["now"])
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("LABEL_READ_TIMEOUT_MAX", "90")
    assert "Rent Burden" in _openai_generate("hello", "model")
    assert "Rent Burden" in _openai_generate("hello", "model")
    line = format_label_latency_summary()
    assert line is not None
    assert "n=2" in line
    assert "45-90s=1" in line
    assert "histogram <30s=1, 30-45s=0, 45-90s=1, >90s=0" in line
    assert label_read_timeout() == configured_label_read_timeout_max() or label_read_timeout() <= 90


def test_read_timeout_cap_is_configurable(monkeypatch):
    monkeypatch.setenv("LABEL_READ_TIMEOUT_MAX", "90")
    assert configured_label_read_timeout_max() == 90.0
    # 80 * 1.5 + 5 = 125, clamped to the configured cap.
    assert compute_read_timeout([80.0] * 10) == 90.0
    monkeypatch.setenv("LABEL_READ_TIMEOUT_MAX", "45")
    assert compute_read_timeout([80.0] * 10) == LABEL_READ_TIMEOUT_MAX
    monkeypatch.setenv("LABEL_READ_TIMEOUT_MAX", "nope")
    assert configured_label_read_timeout_max() == LABEL_READ_TIMEOUT_MAX


def test_slow_cold_start_samples_age_out_after_256():
    for _ in range(8):
        record_label_latency(80.0)
    assert compute_read_timeout([80.0] * 8) == LABEL_READ_TIMEOUT_MAX
    assert label_read_timeout() == LABEL_READ_TIMEOUT_MAX
    for _ in range(256):
        record_label_latency(10.0)
    # The 80s cold-start samples are gone. 10 * 1.5 + 5 = 20, clamped up to 30.
    assert label_read_timeout() == LABEL_READ_TIMEOUT_MIN
    line = format_label_latency_summary()
    assert line is not None
    assert "n=256" in line
    assert "max=10.0s" in line


def test_one_logical_label_is_one_stored_success(monkeypatch):
    """Retries are attempt rows. One successful logical label stores one success."""
    from pipeline.costs import get_meter, reset_meter

    reset_meter()
    calls = {"n": 0}

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Request failed for api.deepinfra.com: timed out")
        return {
            "model": "unit-test-llm",
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "estimated_cost": "0.0001"},
            "choices": [{"message": {"content": "Rent Burden"}}],
        }

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setattr("pipeline.label.time.monotonic", lambda: 50.0 + calls["n"])
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unit-test.deepinfra.com/v1")
    text = _openai_generate("hello", "unit-test-llm")
    assert text == "Rent Burden"
    attempts = get_meter().attempts()
    assert [item.status for item in attempts] == ["retry", "success"]
    assert sum(1 for item in attempts if item.status == "success") == 1
    line = format_label_latency_summary()
    assert line is not None
    assert "n=1" in line


def test_openai_generate_does_not_start_a_read_past_the_deadline(monkeypatch):
    calls = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(timeout)
        raise RuntimeError("Request failed for api.deepinfra.com: timed out")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    set_label_deadline(time.monotonic() + 10)
    with pytest.raises(LabelBudgetExceeded, match="section time budget"):
        _openai_generate("hello", "model")
    assert calls == []


def test_openai_generate_skips_timeout_retry_that_would_pass_the_deadline(monkeypatch):
    """The first read fits. Backoff plus another read does not, so there is no retry."""
    calls = []
    slept = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(url)
        raise RuntimeError("Request failed for api.deepinfra.com: timed out")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    set_label_deadline(time.monotonic() + LABEL_READ_TIMEOUT_DEFAULT + 0.5)
    with pytest.raises(RuntimeError, match="timed out"):
        _openai_generate("hello", "model")
    assert len(calls) == 1
    assert slept == []


def test_openai_generate_skips_429_retry_when_the_next_read_does_not_fit(monkeypatch):
    calls = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(url)
        raise RuntimeError("HTTP 429 from api.deepinfra.com")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    set_label_deadline(time.monotonic() + LABEL_READ_TIMEOUT_DEFAULT + 0.5)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        _openai_generate("hello", "model")
    assert len(calls) == 1


def test_timeout_circuit_stops_retries_after_six_consecutive_timeouts(monkeypatch):
    calls = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(1)
        raise RuntimeError("Request failed for api.deepinfra.com: timed out")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    with pytest.raises(RuntimeError, match="timed out"):
        _openai_generate("hello", "model")
    # Four retries are still allowed: 5 reads, circuit limit is 6.
    assert len(calls) == 5
    assert not timeout_circuit_is_open()
    with pytest.raises(RuntimeError, match="timed out"):
        _openai_generate("hello", "model")
    assert len(calls) == 5 + 1
    assert timeout_circuit_is_open()
    with pytest.raises(RuntimeError, match="timed out"):
        _openai_generate("hello", "model")
    assert len(calls) == 7


def test_timeout_circuit_is_shared_across_workers(monkeypatch):
    calls = []
    lock = threading.Lock()

    def fake_read_json(url, *, timeout, data=None, headers=None):
        with lock:
            calls.append(1)
        raise RuntimeError("Request failed for api.deepinfra.com: timed out")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")

    def worker():
        with pytest.raises(RuntimeError):
            _openai_generate("hello", "model")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # Four workers with four retries each would be 20 POSTs. The shared circuit stops that.
    assert TIMEOUT_CIRCUIT_LIMIT <= len(calls) < 4 * 5
    assert timeout_circuit_is_open()


def test_a_success_clears_the_timeout_streak(monkeypatch):
    calls = {"n": 0}

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls["n"] += 1
        if calls["n"] < 5:
            raise RuntimeError("Request failed for api.deepinfra.com: timed out")
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    assert _openai_generate("hello", "model") == "ok"
    assert not timeout_circuit_is_open()
    calls["n"] = 0

    def always_timeout(url, *, timeout, data=None, headers=None):
        calls["n"] += 1
        raise RuntimeError("Request failed for api.deepinfra.com: timed out")

    monkeypatch.setattr("pipeline.label.read_json", always_timeout)
    with pytest.raises(RuntimeError):
        _openai_generate("hello", "model")
    assert calls["n"] == 5


def test_dead_day_chain_time_versus_ceilings():
    """A dead provider must not run the draft phase past its ceiling."""
    report = dead_provider_worst_case()
    before = report["before"]
    after = report["after"]
    assert report["draft_ceiling"] == 24 * 60
    assert report["section_ceiling"] == 30 * 60
    assert report["unbounded_extra_posts"] == 12 * 16 * 4
    assert report["unbounded_wall_seconds"] == 3680
    assert before["wall_seconds"] > report["draft_ceiling"]
    assert before["extra_posts"] == 288
    assert before["posts"] == 480
    assert before["wall_seconds"] == 1780
    assert after["wall_seconds"] <= report["draft_ceiling"]
    assert after["wall_seconds"] <= report["section_ceiling"]
    assert after["wall_seconds"] == 1440
    assert after["extra_posts"] == 4
    assert after["posts"] == 431
    assert after["extra_posts"] < before["extra_posts"]
    assert format_latency_histogram([10, 40, 60, 120]) == "<30s=1, 30-45s=1, 45-90s=1, >90s=1"


def test_production_90s_chain_runs_past_thirty_minutes():
    """The night this fixes: a 90s ungated read runs the phase past 30 minutes."""
    report = dead_provider_worst_case(read_timeout=90.0, retry_delays=(2.0,))
    assert report["before"]["wall_seconds"] == 2084
    assert report["before"]["wall_seconds"] > report["section_ceiling"]


def test_classify_label_error_buckets():
    assert classify_label_error(RuntimeError("HTTP 429 from api.deepinfra.com")) == "429"
    assert classify_label_error(RuntimeError("HTTP 503 from api.deepinfra.com")) == "5xx"
    assert classify_label_error(RuntimeError("HTTP 500 from api.deepinfra.com")) == "5xx"
    assert classify_label_error(RuntimeError("HTTP 401 from api.deepinfra.com")) == "other"
    assert classify_label_error(RuntimeError("Request failed for api.deepinfra.com: timed out")) == "timeout"
    timeout = RuntimeError("Request failed for api.deepinfra.com: The read operation timed out")
    assert classify_label_error(timeout) == "timeout"
    assert classify_label_error(TimeoutError("timed out")) == "timeout"


def test_openai_generate_does_not_retry_other_errors(monkeypatch):
    calls = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        calls.append(url)
        raise RuntimeError("HTTP 401 from api.deepinfra.com")

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    with pytest.raises(RuntimeError):
        _openai_generate("hello", "model")
    assert len(calls) == 1
