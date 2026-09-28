"""Category rosters so each filter can fill a 10-planet solar system.

Featured topics (the original hand-written ten) live in generate_demo_data.py
and are looked up by name. Extra planets are filled from pipeline.demo_briefs.
"""

from __future__ import annotations

# Ranked loudest → quietest inside each category. The first slots are heavy
# enough that the default "All" solar system is a mix, not one category's entire roster.
CATEGORY_ROSTERS: dict[str, list[str]] = {
    "Technology": [
        "AI Futures",
        "Digital Privacy",
        "Platform Power",
        "Chip Race",
        "Open Source",
        "Cyber Attacks",
        "Smart Cities",
        "Biotech Tools",
        "Space Industry",
        "App Stores",
    ],
    "Economy": [
        "Housing Costs",
        "Labor Markets",
        "Inflation Fight",
        "Small Business",
        "Trade Wars",
        "Care Economy",
        "Wall Street",
        "Student Economy",
        "Crypto Winter",
        "Public Debt",
    ],
    "Politics": [
        "Border Policy",
        "Voting Access",
        "Court Power",
        "Campaign Money",
        "Policing",
        "Foreign Wars",
        "Tax Fights",
        "Statehouses",
        "Protest Rights",
        "Executive Power",
    ],
    "Environment": [
        "Climate Policy",
        "Water Crisis",
        "Grid Transition",
        "Air Quality",
        "Biodiversity",
        "Farm Weather",
        "Plastic Waste",
        "Ocean Heat",
        "Mining Boom",
        "Conservation Land",
    ],
    "Health": [
        "Public Health",
        "Hospital Staffing",
        "Aging Care",
        "Reproductive Care",
        "Addiction Policy",
        "Disability Access",
        "Pandemic Memory",
        "Food Systems",
        "Sleep Crisis",
        "Longevity Hype",
    ],
    "Entertainment": [
        "Franchise Fatigue",
        "Concert Economy",
        "Creator Burnout",
        "Gaming Culture",
        "Streaming Queue",
        "Awards Season",
        "Fandom Wars",
        "Comedy Scene",
        "Theater Revival",
        "Reality TV",
    ],
    "Sports": [
        "Sports Culture",
        "League Labor",
        "College Sports",
        "Soccer Boom",
        "Women's Leagues",
        "Stadium Deals",
        "Esports",
        "Injury Culture",
        "Olympic Politics",
        "Referee Wars",
    ],
    "Education": [
        "Education Reform",
        "College Value",
        "AI in Class",
        "School Safety",
        "Literacy",
        "Admissions",
        "Community College",
        "Faculty Labor",
        "EdTech Fatigue",
        "Civics Teaching",
    ],
    "Media": [
        "Media Trust",
        "Newsroom Cuts",
        "Streaming Wars",
        "Deepfakes",
        "Podcast Politics",
        "Comment Sections",
        "Public Broadcasting",
        "Book Culture",
        "Celebrity News",
        "Documentary Boom",
    ],
    "Religion": [
        "Church and State",
        "Youth Faith",
        "Religious Freedom",
        "Clergy Abuse",
        "Interfaith Cities",
        "Secular Surge",
        "Mutual Aid Faith",
        "Ritual Online",
        "Sacred Land",
        "Evangelical Politics",
    ],
}

# Relative mass of each category in the week. Uneven on purpose so the default
# solar system can include several Politics planets and none from quieter categories.
CATEGORY_WEIGHTS: dict[str, int] = {
    "Technology": 18,
    "Economy": 16,
    "Politics": 13,
    "Environment": 11,
    "Health": 10,
    "Entertainment": 9,
    "Sports": 8,
    "Education": 7,
    "Media": 5,
    "Religion": 3,
}

# Share of a category's mass for planet ranks 1–10 (sun → pluto).
TOPIC_CURVE = [28, 18, 13, 10, 8, 7, 6, 4, 3, 3]
