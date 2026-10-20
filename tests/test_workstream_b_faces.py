"""Off-topic faces, from the newcomer-review issues, word for word.

The strings below are copied from the issue bodies. Nothing is paraphrased.
Where an issue quoted a summary or a face title instead of a post, that is
the string the fixture uses, and the test says so.
"""

from pipeline.grouping import MIN_PLANET_POSTS
from pipeline.label import (
    _text_has_stem,
    face_top_stem,
    faces_are_different_stories,
    majority_story_groups,
    specific_shared_words,
)

# #150. One representative post per face. The issue truncated both with "...".
DATA_CENTERS_TARGETED = (
    "Ukraine has struck Russian tech giant Yandex's data centers, threatening key AI infrastructure..."
)
DATA_CENTERS_HARM = (
    "These data centres aren't being built for our benefit They are being built to reinforce a "
    "police surveillance state..."
)

# #135
ICE_ABUSE = (
    "It is not only the Ice Agent that should be held criminally liable, anyone that was "
    "complicit in that man being given th..."
)
ICE_VOTER = (
    "‘Should Concern All Americans’: Records Show ICE Has Gathered 50 Million Voter Records Ahead of Midterms"
)

# #133
TRANS_RIGHTS = (
    "Gotta love how the average trans person is made of diamond plate and the average cis liberal "
    "crumbles if you merely look..."
)
SITE_SECURITY = (
    "Welp,we've gone behind a login wall for the night. Didn't want to. The AI corps and their "
    "scraperbot armies made it impossible to open as the site just goes straight down under the onslaught."
)

# #118 quoted summaries, not posts.
CANADIAN_SEPARATISM = "Some Canadians support separation from Canada"
US_THREATENS_CANADA = "US threatens Canada's sovereignty"

# #109
ANGIE_NIXON = "I better see every progressive in Florida voting for Angie Nixon..."
ELECTION_FRAUD = [
    "The only times she hasn't voted with trump, mitch gave her special dispensation...",
    "It was a fraud. Justice Sandra Day O'Connor, who was the deciding vote, later said she regretted it...",
]

# #177. The issue quoted the Don't Run posts and the face titles, not the Kamala posts.
KAMALA_FALTERS = "Kamala Falters"
DONT_RUN = [
    "The only way Danielle is going to win. The next election is through a pity vote. She has already "
    "started that with her oil tears a couple of weeks ago. Don’t fall for it.",
    "I can’t believe the people of Maine continue to elect her. But I live in Tennessee. I don’t have room to talk.",
    "She only ever votes No when she knows her vote doesn’t matter to the outcome. Her & Murkowski.",
]

# #203. One face. The planet has 5 posts.
TOILET_PAPER = [
    "Were the attackers of the men women?",
    "They ran out of toilet paper and then men are blaming the women for using more 🫩 #bb1",
    "Mashup of 2 Women, 2 different incidents. One had a happy ending. The other did not. "
    "Bird woman walked out defiantly in a Primus tee. The other was brutally beaten by 5 real men and arrested.",
]

# #174
OMAR_RAID = [
    "AP, why are you always trying to make crap like this seem like a normal, everyday thing … Federal "
    "agents search Rep. Ilhan Omar's home as part of a criminal inv",
    "BREAKING: Feds have searched the DC home of Rep. Omar. Allegedly connected to her immigration "
    "paperwork. Most will not find this surprising as trump has hated o",
    "The Politically Motivated Raid and Intimidation Of Rep Ilhan Omar...The Wash "
    "wwwgodandi.blogspot.com/2026/10/the-...",
]
TRUMP_INVESTIGATION = [
    "The fact that media sympathetic to Trump describes it as a criminal investigation about her "
    "immigration paperwork, all of which was submitted before she was 18 ",
    "Huh I wonder if we could open up a criminal fraud investigation into Kimbal and Elon musk’s "
    "immigration paperwork considering public evidence",
    "“Criminal” investigation? Who the F wrote that? Whats “criminal” is the actual investigation.",
    "It was clear long ago these investigations were never about crime. They were punishment for "
    "political disagreement, brought at the president’s urging against pe",
]


def _face(title, texts, post_count):
    return {
        "title": title,
        "post_count": post_count,
        "representative_posts": [{"text": text} for text in texts],
    }


def _split(faces):
    groups = majority_story_groups(faces)
    assert groups is not None and len(groups) >= 2
    assert faces_are_different_stories(faces) is True
    return groups


def test_issue_150_data_centers_faces_are_different_stories():
    faces = [
        _face("Data Centers Targeted", [DATA_CENTERS_TARGETED], 52),
        _face("Data Centers Harm", [DATA_CENTERS_HARM], 4),
    ]
    # The old check stays glued: both posts say "data".
    assert specific_shared_words(faces)
    _split(faces)


def test_issue_135_ice_abuse_and_voter_records_split():
    faces = [
        _face("ICE Abuse", [ICE_ABUSE], 47),
        _face("ICE Voter Probe", [ICE_VOTER], 19),
    ]
    _split(faces)


def test_issue_133_site_security_leaves_trans_rights():
    faces = [
        _face("Trans Rights", [TRANS_RIGHTS], 66),
        _face("Site Security", [SITE_SECURITY], 4),
    ]
    _split(faces)


def test_issue_118_separatism_summaries_are_different_stories():
    # The issue gave summaries and shares, not posts. 50.9% and 49.1% of 57.
    faces = [
        _face("Canadian Separatism", [CANADIAN_SEPARATISM], 29),
        _face("US Threatens Canada", [US_THREATENS_CANADA], 28),
    ]
    assert specific_shared_words(faces)  # glued by "canada" today
    _split(faces)


def test_issue_109_election_fraud_leaves_angie_nixon():
    # Shares were 55% and 45%. The issue did not give post counts.
    faces = [
        _face("Angie Nixon", [ANGIE_NIXON], 55),
        _face("Election Fraud", ELECTION_FRAUD, 45),
    ]
    assert specific_shared_words(faces)  # glued by "vote"
    _split(faces)


def test_issue_177_dont_run_posts_are_not_about_kamala():
    # No Kamala post was quoted. The face title is the verbatim majority text.
    faces = [
        _face(KAMALA_FALTERS, [], 31),
        _face("Don't Run", DONT_RUN, 10),
    ]
    groups = _split(faces)
    assert groups[0] == [0]
    assert [1] in groups


def test_issue_203_toilet_paper_is_one_face_under_the_floor():
    faces = [_face("Women Attacked", TOILET_PAPER, 5)]
    assert majority_story_groups(faces) == [[0]]
    assert 5 < MIN_PLANET_POSTS


def test_issue_174_omar_and_the_investigation_do_not_share_a_top_stem():
    """A top-stem merge would not join these planets. It is not shipped."""
    omar = face_top_stem(OMAR_RAID)
    investigation = face_top_stem(TRUMP_INVESTIGATION)
    assert omar is not None and investigation is not None
    assert omar != investigation
    covered = sum(1 for text in TRUMP_INVESTIGATION if _text_has_stem(text, omar))
    assert covered / len(TRUMP_INVESTIGATION) < 0.5


def test_faces_that_repeat_the_largest_stem_stay_one_story():
    faces = [
        _face(
            "Iran War",
            ["Iran is at war in the Strait of Hormuz.", "The Iran war widened today."],
            10,
        ),
        _face(
            "Iran Attacks Ships",
            ["Iran attacked ships in the Strait of Hormuz.", "Iranian missiles hit a ship."],
            4,
        ),
    ]
    assert majority_story_groups(faces) == [[0, 1]]
    assert faces_are_different_stories(faces) is False
