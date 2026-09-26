"""Generate the static Discourse Universe payload used by the frontend.

Until the live Bluesky → BERTopic → LLM pipeline lands, this module writes a
schema-compatible demo `public/data.json` so the visualization can be designed
and shipped independently of the NLP work.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from pipeline.schema import NOISE_POLICY, validate_payload

DEMO_TOTAL_POSTS = 100_000
DEMO_LAST_UPDATED = date(2026, 9, 26).isoformat()
DEMO_CATEGORIES = {
    1: "Technology",
    2: "Economy",
    3: "Environment",
    4: "Health",
    5: "Economy",
    6: "Politics",
    7: "Technology",
    8: "Education",
    9: "Sports",
    10: "Media",
}

# Topics are ordered by volume. Topic 1 is the sun at the origin.
DEMO_TOPICS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "AI Futures",
        "total_volume_percent": 22.4,
        "perspectives": [
            {
                "id": "1A",
                "title": "Job Displacement",
                "summary": "People are tracking layoffs and wondering which white-collar roles survive the next model release.",
                "volume_percent": 28.0,
                "representative_posts": [
                    {"author": "maya.bsky", "text": "Third agency this month replaced their junior writers with an LLM. This is not a vibe, it is a payroll strategy.", "likes": 1840},
                    {"author": "unionize.dev", "text": "If your job is 'summarize the meeting', the meeting is already the product. Automating you was the easy part.", "likes": 992},
                    {"author": "careershelf", "text": "Career counselor today told a room of new grads to 'become AI-proof'. Nobody could define what that means.", "likes": 741},
                ],
            },
            {
                "id": "1B",
                "title": "Acceleration Optimism",
                "summary": "A loud cohort treats faster models as a civilizational upgrade and wants fewer brakes, not more.",
                "volume_percent": 22.0,
                "representative_posts": [
                    {"author": "buildfast", "text": "The productivity jump from local models this year is real. I shipped in a weekend what used to take a squad.", "likes": 1304},
                    {"author": "nova.codes", "text": "We are arguing about feelings while a billion people just got a free research assistant. Scale is the moral story.", "likes": 886},
                    {"author": "garage-lab", "text": "Open weights are the printing press. The panic is the same genre as every other literacy panic.", "likes": 512},
                ],
            },
            {
                "id": "1C",
                "title": "Safety Alignment",
                "summary": "Researchers and bystanders keep returning to loss-of-control, evals, and whether labs will slow down.",
                "volume_percent": 17.0,
                "representative_posts": [
                    {"author": "evalwatch", "text": "Capability demos dropped. The public eval suite did not. That gap is the actual news.", "likes": 1102},
                    {"author": "redteam.bsky", "text": "I do not need sci-fi. I need labs to publish what their models will not refuse next quarter.", "likes": 640},
                    {"author": "slowtake", "text": "Alignment is not a vibe check. If you cannot measure it, you are fundraising, not governing.", "likes": 401},
                ],
            },
            {
                "id": "1D",
                "title": "Creative Labor",
                "summary": "Artists and performers frame generative tools as unpaid training on their catalogs.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "inkstudy", "text": "My style is in six commercial models and I was never asked. That is not inspiration, that is inventory.", "likes": 2104},
                    {"author": "session-musician", "text": "Labels want infinite cheap stems. They still want a human face for the encore. Guess who gets the contract.", "likes": 733},
                    {"author": "comicgrid", "text": "Commission market is weird now. Clients send a generated rough and ask me to 'make it not look generated'.", "likes": 588},
                ],
            },
            {
                "id": "1E",
                "title": "Energy Footprint",
                "summary": "The cluster boom is being read as a climate and utilities story, not just a software story.",
                "volume_percent": 11.0,
                "representative_posts": [
                    {"author": "gridnotes", "text": "Our town's next substation is sized for a training campus, not households. That should be a public meeting.", "likes": 976},
                    {"author": "hydro.watch", "text": "Water-cooled racks in a drought basin is the kind of sentence that used to live in a dystopian novel.", "likes": 654},
                    {"author": "wattmeter", "text": "I want the model card to include megawatts. Tokens are not a unit of accountability.", "likes": 390},
                ],
            },
            {
                "id": "1F",
                "title": "Everyday Copilots",
                "summary": "The quieter majority is just using assistants for mail, homework, and small workarounds.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "tuesday.admin", "text": "I do not care about AGI. I care that it drafted the insurance appeal I had been avoiding for six weeks.", "likes": 1608},
                    {"author": "dad-of-three", "text": "Helped my kid outline a history essay. The useful part was the questions, not the paragraphs.", "likes": 422},
                    {"author": "clinic.front", "text": "We use it to translate after-visit notes. Imperfect, but the alternative was sending people home confused.", "likes": 311},
                ],
            },
        ],
    },
    {
        "id": 2,
        "name": "Housing Costs",
        "total_volume_percent": 16.8,
        "perspectives": [
            {
                "id": "2A",
                "title": "Rent Burden",
                "summary": "A dominant thread treats rent as the organizing fact of adult life, crowding out every other plan.",
                "volume_percent": 40.0,
                "representative_posts": [
                    {"author": "leasehold", "text": "Half my take-home is a one-bedroom that failed inspection twice. The market is not a weather system.", "likes": 2411},
                    {"author": "roomate-math", "text": "I have a graduate degree and three roommates. That sentence should not still be true at 34.", "likes": 1330},
                    {"author": "citybus", "text": "Moved an hour out to afford a studio. My 'housing win' is a 2am last-train lifestyle.", "likes": 804},
                ],
            },
            {
                "id": "2B",
                "title": "Zoning Reform",
                "summary": "YIMBY arguments keep pointing at parking minimums, single-family maps, and hearing-room vetoes.",
                "volume_percent": 18.0,
                "representative_posts": [
                    {"author": "missingmiddle", "text": "We legalized duplexes and then spent a year inventing new ways to make them illegal in practice.", "likes": 990},
                    {"author": "transit.maps", "text": "If a train stop is surrounded by lawns, that is a policy choice, not a housing shortage mystery.", "likes": 712},
                    {"author": "council-notes", "text": "Same ten homeowners show up, same 'neighborhood character' line, same empty lots. Character is a zoning code.", "likes": 501},
                ],
            },
            {
                "id": "2C",
                "title": "Homeownership Gap",
                "summary": "Younger buyers describe down payments and insurance as a locked door, not a ladder.",
                "volume_percent": 16.0,
                "representative_posts": [
                    {"author": "firststair", "text": "Saved for five years. Insurance quotes ate the entire buffer in one renewal cycle.", "likes": 1204},
                    {"author": "ratewatch", "text": "My parents bought on one income. I cannot get a preapproval with two and a side gig.", "likes": 867},
                    {"author": "creditdust", "text": "Starter homes are investment products now. Families are bidding against someone's portfolio allocation.", "likes": 633},
                ],
            },
            {
                "id": "2D",
                "title": "Investor Landlords",
                "summary": "Corporate owners and short-term rentals are blamed for turning shelter into a yield strategy.",
                "volume_percent": 12.0,
                "representative_posts": [
                    {"author": "blockwatch", "text": "Twelve units on my street went to an LLC last year. None of those doors have names on the buzzer anymore.", "likes": 1544},
                    {"author": "host-fatigue", "text": "The building is half Airbnbs. We live in a hallway of suitcases and key-lock boxes.", "likes": 688},
                    {"author": "maintenance-q", "text": "Filed the same leak with a chatbot portal for 40 days. Private equity does not own a plunger.", "likes": 470},
                ],
            },
            {
                "id": "2E",
                "title": "Construction Costs",
                "summary": "Builders and trades focus on materials, insurance, and the time tax of permits.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "site-lead", "text": "Lumber calmed down. Insurance and interest did not. That is why the mid-rise died at the drawing set.", "likes": 412},
                    {"author": "trade-school", "text": "We do not have a labor myth, we have a pipeline. Four-year degrees will not frame this city.", "likes": 355},
                    {"author": "permit-desk", "text": "Eighteen months to approve a four-story building is a housing policy, whether anyone voted on it or not.", "likes": 298},
                ],
            },
            {
                "id": "2F",
                "title": "Remote Relocate",
                "summary": "A smaller group is still trying to arbitrage rent by leaving coastal job centers.",
                "volume_percent": 6.0,
                "representative_posts": [
                    {"author": "two-timezones", "text": "Left the bay, kept the job, lost the friends. Housing got cheaper. Life got thinner.", "likes": 720},
                    {"author": "midwest-desk", "text": "Remote let me buy. Hybrid yanked me back two days a week. The math no longer closes.", "likes": 366},
                    {"author": "nomad-tax", "text": "Every cheap city I loved is now pricing like it read the same newsletter.", "likes": 240},
                ],
            },
        ],
    },
    {
        "id": 3,
        "name": "Climate Policy",
        "total_volume_percent": 12.1,
        "perspectives": [
            {
                "id": "3A",
                "title": "Extreme Weather",
                "summary": "Lived experience of heat, flood, and fire is doing more persuading than any report abstract.",
                "volume_percent": 32.0,
                "representative_posts": [
                    {"author": "smoke-season", "text": "We canceled recess again. Kids can identify AQI colors before they can identify state birds.", "likes": 1888},
                    {"author": "river-row", "text": "Third flood in five years. FEMA is a form, not a plan, and my street knows the difference.", "likes": 940},
                    {"author": "night-heat", "text": "The power stayed on. The nights did not cool. That is the new definition of a lucky summer.", "likes": 511},
                ],
            },
            {
                "id": "3B",
                "title": "Adaptation Funding",
                "summary": "Local officials want money for shade, pumps, and grids rather than another target-year slogan.",
                "volume_percent": 20.0,
                "representative_posts": [
                    {"author": "city-budget", "text": "I can pass a net-zero resolution in an afternoon. A cooling center takes a line item and a fight.", "likes": 802},
                    {"author": "coastal-eng", "text": "Retreat is a planning word. On the ground it is buyouts, arguments, and people who will not leave.", "likes": 544},
                    {"author": "mutual-aid", "text": "When the county map is late, neighbors become infrastructure. That should embarrass someone paid.", "likes": 390},
                ],
            },
            {
                "id": "3C",
                "title": "Fossil Phaseout",
                "summary": "Campaigners keep pressure on permits, banks, and the remaining expansion projects.",
                "volume_percent": 16.0,
                "representative_posts": [
                    {"author": "keep-it-down", "text": "A new terminal is not a transition. It is a 40-year bet that the math is optional.", "likes": 1011},
                    {"author": "divest-now", "text": "If your pension still underwrites the expansion, the postcard from the beach is paid for twice.", "likes": 476},
                    {"author": "permian-watch", "text": "Flaring at night looks like a city. It is not a city. It is wasted gas and a permission structure.", "likes": 322},
                ],
            },
            {
                "id": "3D",
                "title": "Green Jobs",
                "summary": "Labor voices want the energy shift to show up as apprenticeships and wages, not just press releases.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "ibe-local", "text": "I will install the transition. I will not applaud a tax credit that skips the union hall.", "likes": 733},
                    {"author": "auto-line", "text": "EV retooling is real. The question is who keeps the pension when the badge changes.", "likes": 481},
                    {"author": "weatherize", "text": "Heat-pump techs are booked eight weeks out. That is demand. Train people like you mean it.", "likes": 350},
                ],
            },
            {
                "id": "3E",
                "title": "Climate Delay",
                "summary": "Skeptics and exhausted centrists argue the timeline is theatrical and the costs are being hidden.",
                "volume_percent": 10.0,
                "representative_posts": [
                    {"author": "cost-first", "text": "I believe the atmosphere. I do not believe every subsidy is a climate policy. Some of it is industrial fanfic.", "likes": 690},
                    {"author": "grid-realist", "text": "Shut the plant before the replacement exists and you have not decarbonized. You have exported the smoke.", "likes": 512},
                    {"author": "wait-and-see", "text": "We have been two years from breakthrough since I was in school. Forgive the eye roll.", "likes": 288},
                ],
            },
            {
                "id": "3F",
                "title": "Nuclear Debate",
                "summary": "A persistent minority treats fission as the adult option the coalition still will not say out loud.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "atoms-ok", "text": "If your climate plan needs weather to cooperate, it is a hope, not a grid.", "likes": 844},
                    {"author": "old-plant", "text": "We closed a working reactor and fired up gas. Please stop calling that a win in the newsletter.", "likes": 601},
                    {"author": "waste-faq", "text": "The waste argument is serious. So is cooking the rivers. Rank the risks like an engineer.", "likes": 274},
                ],
            },
        ],
    },
    {
        "id": 4,
        "name": "Public Health",
        "total_volume_percent": 10.4,
        "perspectives": [
            {
                "id": "4A",
                "title": "Access Barriers",
                "summary": "Wait times, closed panels, and geography still dominate how people talk about getting care.",
                "volume_percent": 30.0,
                "representative_posts": [
                    {"author": "hold-music", "text": "Six months for a primary care intake. That is not a system, that is a lottery with copays.", "likes": 1720},
                    {"author": "night-shift-rn", "text": "We are not short on compassion. We are short on beds, nurses, and anyone who can stay past year three.", "likes": 988},
                    {"author": "no-panel", "text": "Insurance card in hand. Every nearby clinic: not accepting new patients. The card is a brochure.", "likes": 640},
                ],
            },
            {
                "id": "4B",
                "title": "Drug Pricing",
                "summary": "Insulin, inhalers, and new weight-loss drugs keep collapsing the conversation into list prices.",
                "volume_percent": 22.0,
                "representative_posts": [
                    {"author": "rx-stub", "text": "The coupon expired, the price tripled, the molecule did not change. Explain that without using the word 'market'.", "likes": 1502},
                    {"author": "pharmacy-tech", "text": "I spend half my day calling around for a fill people already paid insurance to theoretically have.", "likes": 711},
                    {"author": "glp1-wait", "text": "A shortage of a celebrity drug should not crowd out thyroid meds. Priorities are a choice.", "likes": 455},
                ],
            },
            {
                "id": "4C",
                "title": "Mental Health",
                "summary": "Therapy access, youth distress, and burnout remain a parallel system people assemble themselves.",
                "volume_percent": 18.0,
                "representative_posts": [
                    {"author": "waitlist", "text": "The hotline was kind. The intake was 14 weeks. Kindness is not capacity.", "likes": 1208},
                    {"author": "school-couns", "text": "I have 700 students and a closet office. That is the youth mental health plan in one sentence.", "likes": 870},
                    {"author": "shift-end", "text": "We told everyone to destigmatize therapy and then made it a luxury good. Bold strategy.", "likes": 503},
                ],
            },
            {
                "id": "4D",
                "title": "Insurance Maze",
                "summary": "Prior auth, networks, and denied claims are treated as the real clinical bottleneck.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "denied-again", "text": "The scan is medically necessary until a person who has never met me decides it is educational.", "likes": 1344},
                    {"author": "billing-dept", "text": "I am a nurse who now speaks 'appeals'. That is not why I sat for the boards.", "likes": 612},
                    {"author": "in-network", "text": "The surgeon was in-network. The anesthesiologist was a surprise. This country loves plot twists.", "likes": 488},
                ],
            },
            {
                "id": "4E",
                "title": "Rural Hospitals",
                "summary": "Closures and long ambulance rides make care a distance problem before it is a science problem.",
                "volume_percent": 9.0,
                "representative_posts": [
                    {"author": "county-er", "text": "Labor and delivery is 90 minutes away. That is a policy outcome with a county name on it.", "likes": 902},
                    {"author": "volunteer-emt", "text": "We lost the hospital and kept the highway. Guess which one people still need at 2am.", "likes": 544},
                    {"author": "clinic-tues", "text": "Specialists fly in twice a month. Chronic illness does not keep that calendar.", "likes": 231},
                ],
            },
            {
                "id": "4F",
                "title": "Wellness Culture",
                "summary": "A smaller, louder stream sells protocols, wearables, and suspicion of institutions as health itself.",
                "volume_percent": 7.0,
                "representative_posts": [
                    {"author": "protocol-guy", "text": "Your PCP has 12 minutes. My spreadsheet has 40 biomarkers. I know which one feels like care.", "likes": 377},
                    {"author": "seed-oil-hr", "text": "I do not trust the food pyramid or the podcast that replaced it. That is the whole genre.", "likes": 290},
                    {"author": "step-count", "text": "The watch thinks I am thriving. My bloodwork is more honest than my streaks.", "likes": 188},
                ],
            },
        ],
    },
    {
        "id": 5,
        "name": "Labor Markets",
        "total_volume_percent": 9.2,
        "perspectives": [
            {
                "id": "5A",
                "title": "Wage Stagnation",
                "summary": "Workers keep stacking raises against rent and groceries and calling the remainder a disappearance.",
                "volume_percent": 26.0,
                "representative_posts": [
                    {"author": "paycheck-math", "text": "4% raise, 9% everything else. HR called it a strong year. My cart disagreed.", "likes": 1666},
                    {"author": "tipped-out", "text": "We are 'essential' on the window cling and optional on the schedule. Pick one.", "likes": 802},
                    {"author": "salary-band", "text": "Posted range starts below last year's median. The ghost job is a negotiating tactic.", "likes": 544},
                ],
            },
            {
                "id": "5B",
                "title": "Union Revival",
                "summary": "New organizing drives treat a card campaign as the only remaining leverage.",
                "volume_percent": 20.0,
                "representative_posts": [
                    {"author": "card-check", "text": "We won the vote. Then the bargaining calendar became the new battlefield. Expected, still exhausting.", "likes": 911},
                    {"author": "warehouse-a2", "text": "They flew in the consultants the day after we asked for water and a fan. Subtle.", "likes": 703},
                    {"author": "grad-worker", "text": "If the university can find money for a stadium, it can find money for the people grading the exams.", "likes": 588},
                ],
            },
            {
                "id": "5C",
                "title": "Gig Precarity",
                "summary": "App-based work is described as flexibility with the safety rails removed.",
                "volume_percent": 18.0,
                "representative_posts": [
                    {"author": "last-mile", "text": "I am a contractor until the algorithm wants a uniform. Then I am a brand.", "likes": 1004},
                    {"author": "rideshare-am", "text": "Quest bonus vanished, insurance did not. Flexibility is a slogan that does not jump a dead battery.", "likes": 612},
                    {"author": "shopper-notes", "text": "Customer tips on vibes. The app tips on silence. Neither is a wage.", "likes": 401},
                ],
            },
            {
                "id": "5D",
                "title": "Return To Office",
                "summary": "Badge-in mandates remain a trust fight between managers and people who rebuilt their lives around remote.",
                "volume_percent": 16.0,
                "representative_posts": [
                    {"author": "badge-swipe", "text": "Three days in for meetings that are still on Zoom because half the team is in another tower.", "likes": 1422},
                    {"author": "manager-view", "text": "I do not miss surveillance. I miss the hallway corrections that never become a ticket.", "likes": 509},
                    {"author": "commute-tax", "text": "Office policy is a pay cut that does not appear on the offer letter.", "likes": 733},
                ],
            },
            {
                "id": "5E",
                "title": "Skills Gap",
                "summary": "Employers say they cannot hire; applicants say the posts are wish lists with salary theater.",
                "volume_percent": 12.0,
                "representative_posts": [
                    {"author": "junior-ban", "text": "Five years experience for a tool that is three years old. The skills gap is a fiction we all act in.", "likes": 1288},
                    {"author": "apprentice-me", "text": "Stop asking for unicorns. Hire a human and spend six months teaching them the stack.", "likes": 640},
                    {"author": "hr-systems", "text": "The ATS rejected the internal candidate. We built a maze and then complained it was empty.", "likes": 355},
                ],
            },
            {
                "id": "5F",
                "title": "Automation Spillover",
                "summary": "Warehouse and office staff describe software as the new supervisor, not a teammate.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "pick-rate", "text": "The scanner tells me I am 12% behind a number nobody can explain. That is management now.", "likes": 770},
                    {"author": "claims-bot", "text": "They automated the easy cases and left humans the screaming ones. Efficiency for whom?", "likes": 412},
                    {"author": "qa-night", "text": "I review the model. The model reviews my review time. Funhouse mirrors, but with KPIs.", "likes": 260},
                ],
            },
        ],
    },
    {
        "id": 6,
        "name": "Border Policy",
        "total_volume_percent": 8.1,
        "perspectives": [
            {
                "id": "6A",
                "title": "Asylum Backlog",
                "summary": "Case workers and migrants describe a queue so long it functions as a policy by itself.",
                "volume_percent": 27.0,
                "representative_posts": [
                    {"author": "docket-404", "text": "A hearing date in 2029 is not due process. It is a waiting room with no chairs.", "likes": 990},
                    {"author": "shelter-night", "text": "We ran out of mats before we ran out of families. The backlog has an address this week.", "likes": 712},
                    {"author": "form-i", "text": "Lost my work permit in a processing hole. I can stay. I cannot legally earn. That is the trap.", "likes": 501},
                ],
            },
            {
                "id": "6B",
                "title": "Labor Shortage",
                "summary": "Farms, kitchens, and care homes keep asking where legal workers are supposed to come from.",
                "volume_percent": 21.0,
                "representative_posts": [
                    {"author": "orchard-am", "text": "Fruit does not wait for a visa category. Either we pick it or we import it already picked.", "likes": 808},
                    {"author": "kitchen-lead", "text": "I can raise wages. I cannot summon a line cook from a closed legal channel.", "likes": 544},
                    {"author": "home-care", "text": "Aging towns need hands. The debate is happening as if the patients can postpone.", "likes": 390},
                ],
            },
            {
                "id": "6C",
                "title": "Border Enforcement",
                "summary": "A hard-line cluster wants crossings treated as a capacity and deterrence problem first.",
                "volume_percent": 18.0,
                "representative_posts": [
                    {"author": "sector-south", "text": "If the rule is optional at the line, it is optional everywhere. That is not xenophobia, it is arithmetic.", "likes": 1201},
                    {"author": "small-town-pd", "text": "We are not a port of entry. We became one by neglect, and we do not have the budget for the plot twist.", "likes": 633},
                    {"author": "order-first", "text": "Humanitarian language without a queue is how you get neither humanity nor a line.", "likes": 480},
                ],
            },
            {
                "id": "6D",
                "title": "Community Strain",
                "summary": "Mayors and school boards talk about beds, classrooms, and buses rather than slogans.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "school-board", "text": "We enrolled 400 new students in a year. The budget did not get the same letter.", "likes": 702},
                    {"author": "shelter-mayor", "text": "Compassion without reimbursement is just a city credit card. Say that out loud in the hearing.", "likes": 511},
                    {"author": "bus-barn", "text": "Hotels as housing is an emergency move that calcified. Emergencies are supposed to end.", "likes": 288},
                ],
            },
            {
                "id": "6E",
                "title": "Family Reunification",
                "summary": "Personal stories keep returning to visas, years of separation, and paperwork as a life sentence.",
                "volume_percent": 12.0,
                "representative_posts": [
                    {"author": "wait-year-12", "text": "My sibling is not a statistic. She is a file that has been 'in process' since my nephew learned to walk.", "likes": 844},
                    {"author": "spouse-visa", "text": "Marriage is legal. The appointment calendar is the actual immigration system.", "likes": 490},
                    {"author": "daca-still", "text": "I have a degree, a job, and a renewal ritual. Permanence should not be a PDF.", "likes": 377},
                ],
            },
            {
                "id": "6F",
                "title": "Refugee Welcome",
                "summary": "A smaller welcome-first group emphasizes resettlement capacity and post-war obligations.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "sponsor-home", "text": "We had a spare room and a legal pathway. That combination should not feel rare.", "likes": 560},
                    {"author": "church-base", "text": "The families we hosted are on payrolls now. The scare stories never do a follow-up episode.", "likes": 412},
                    {"author": "resettle-ops", "text": "Welcome is logistics: rent, language, a dentist. Speeches are the cheap part.", "likes": 240},
                ],
            },
        ],
    },
    {
        "id": 7,
        "name": "Digital Privacy",
        "total_volume_percent": 7.3,
        "perspectives": [
            {
                "id": "7A",
                "title": "Surveillance Ads",
                "summary": "People are tired of feeling followed from a search to a couch to a billboard.",
                "volume_percent": 29.0,
                "representative_posts": [
                    {"author": "ad-shadow", "text": "I mentioned a crib once in a voice note. The feed already had a registry. That is not coincidence, that is a dossier.", "likes": 1555},
                    {"author": "opt-out-maze", "text": "The privacy dashboard has 40 toggles and one business model. Guess which one wins.", "likes": 802},
                    {"author": "bus-stop-ad", "text": "When the billboard knows my cart, public space is just another slot.", "likes": 344},
                ],
            },
            {
                "id": "7B",
                "title": "Data Brokers",
                "summary": "Broker files, people-search sites, and leaked location history keep showing up as a hidden market.",
                "volume_percent": 20.0,
                "representative_posts": [
                    {"author": "delete-me", "text": "I paid a service to remove me from 80 sites. 12 came back in a month. Whack-a-mole is not a right.", "likes": 977},
                    {"author": "loc-leak", "text": "A broker sold 'sensitive location' pings. The category name is already a confession.", "likes": 640},
                    {"author": "skiptrace", "text": "My home address is a product. I did not list it. Someone else made a SKU.", "likes": 401},
                ],
            },
            {
                "id": "7C",
                "title": "Device Lock-in",
                "summary": "Repair, sideloading, and account gates are framed as ownership that expires at the login screen.",
                "volume_percent": 17.0,
                "representative_posts": [
                    {"author": "right-to-fix", "text": "A $1,200 phone that refuses a $20 battery is a rental with extra steps.", "likes": 1308},
                    {"author": "sideload", "text": "If I cannot install software I trust, I do not own a computer. I own a showroom.", "likes": 733},
                    {"author": "cloud-key", "text": "Lost the account, lost the photos, lost the documents. The hardware is a paperweight with a camera.", "likes": 512},
                ],
            },
            {
                "id": "7D",
                "title": "Encryption Rights",
                "summary": "Security folks treat client-side scanning and backdoor bills as the same old key-escrow fight.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "signal-fan", "text": "A backdoor for the good guys is a front door for everyone else. Math does not do nationalities.", "likes": 888},
                    {"author": "threat-model", "text": "Journalists, clinics, and shelters need the same cryptography as hobbyists. That is the point.", "likes": 477},
                    {"author": "csam-scan", "text": "Scan-on-device is still a surveillance architecture. Rename it as many times as you want.", "likes": 310},
                ],
            },
            {
                "id": "7E",
                "title": "Kids Online",
                "summary": "Parents want defaults that assume a child, not another terms-of-service checkbox.",
                "volume_percent": 12.0,
                "representative_posts": [
                    {"author": "parent-mode", "text": "The app is free because my 12-year-old is the inventory. I would like that sentence in the onboarding.", "likes": 1402},
                    {"author": "school-tablet", "text": "District issued devices, district issued trackers. Homework should not be a telemetry event.", "likes": 566},
                    {"author": "age-gate", "text": "A checkbox that says I am 18 is not a child-safety program. It is a liability fig leaf.", "likes": 388},
                ],
            },
            {
                "id": "7F",
                "title": "Open Source Hope",
                "summary": "A hopeful minority still treats local software and audits as an exit from the attention market.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "self-host", "text": "Moved photos off the big cloud. I am now the unreliable vendor, but at least I am not the product.", "likes": 612},
                    {"author": "foss-friday", "text": "The boring tools are the freedom tools. Nobody influencers a calendar you can grep.", "likes": 290},
                    {"author": "local-llm", "text": "A model on my desk cannot quietly update its privacy policy at 3am. That is a feature.", "likes": 255},
                ],
            },
        ],
    },
    {
        "id": 8,
        "name": "Education Reform",
        "total_volume_percent": 5.8,
        "perspectives": [
            {
                "id": "8A",
                "title": "Student Debt",
                "summary": "Borrowers treat repayment math as a second rent that follows them between jobs.",
                "volume_percent": 31.0,
                "representative_posts": [
                    {"author": "servicer-bot", "text": "I have paid for 11 years and the principal waved hello. That is not a loan, that is a subscription.", "likes": 2011},
                    {"author": "plus-loan", "text": "My parents borrowed for my degree. The family balance sheet is the actual diploma.", "likes": 733},
                    {"author": "community-first", "text": "I skipped the private campus. Still drowning in certificates that expired before the job did.", "likes": 401},
                ],
            },
            {
                "id": "8B",
                "title": "Teacher Pay",
                "summary": "Educators describe second jobs and empty candidate pools as the real classroom crisis.",
                "volume_percent": 20.0,
                "representative_posts": [
                    {"author": "room-204", "text": "I buy the paper. I buy the snacks. I cannot buy another year of this at this wage.", "likes": 1660},
                    {"author": "sub-shortage", "text": "Prep period is now coverage. The shortage is a staffing model, not a surprise.", "likes": 812},
                    {"author": "quit-june", "text": "Left for a district with childcare. That is recruitment. Housing and pay are pedagogy.", "likes": 544},
                ],
            },
            {
                "id": "8C",
                "title": "Curriculum Wars",
                "summary": "Boards and parents fight over what counts as history, gender, and age-appropriate reading.",
                "volume_percent": 17.0,
                "representative_posts": [
                    {"author": "shelf-check", "text": "We are debating a novel while the library lost its clerk. Censorship is easier than staffing.", "likes": 990},
                    {"author": "parent-rights", "text": "I want the reading list before the unit starts. That is not a raid, it is a syllabus.", "likes": 640},
                    {"author": "ap-hist", "text": "If the standard changes every election, we are not teaching history. We are teaching the news cycle.", "likes": 377},
                ],
            },
            {
                "id": "8D",
                "title": "Childcare Crunch",
                "summary": "Families describe slots, waitlists, and infant care as the hidden first school system.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "waitlist-0", "text": "Pregnant and already 18th on a list. The labor market starts before labor.", "likes": 1220},
                    {"author": "center-close", "text": "The only infant room in town closed. Two careers became one overnight.", "likes": 701},
                    {"author": "pre-k-gap", "text": "Universal pre-k that ends at 2pm is a press conference, not childcare.", "likes": 455},
                ],
            },
            {
                "id": "8E",
                "title": "Campus Speech",
                "summary": "Universities remain a stage for protest rules, donor pressure, and what counts as harassment.",
                "volume_percent": 10.0,
                "representative_posts": [
                    {"author": "quad-noon", "text": "A university that cannot hold a disagreement without a lock-down is not a university that week.", "likes": 812},
                    {"author": "title-ix", "text": "Safety is real. So is the temptation to use safety as a mute button. Both can be true.", "likes": 490},
                    {"author": "adjunct-mic", "text": "I have no tenure and a viral clip. Academic freedom is a feeling reserved for other people.", "likes": 333},
                ],
            },
            {
                "id": "8F",
                "title": "Vocational Paths",
                "summary": "A growing group wants shop, nursing, and trades treated as first-class routes, not leftovers.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "shop-class", "text": "We killed the auto shop, then acted shocked that nobody can afford a mechanic.", "likes": 1408},
                    {"author": "rn-bridge", "text": "The fastest respectable ladder in my town is still a two-year nursing program. Fund it like you mean it.", "likes": 566},
                    {"author": "apprentice-17", "text": "I make more than my cousin with the thesis. The guidance office still calls this a backup plan.", "likes": 402},
                ],
            },
        ],
    },
    {
        "id": 9,
        "name": "Sports Culture",
        "total_volume_percent": 4.6,
        "perspectives": [
            {
                "id": "9A",
                "title": "Athlete Power",
                "summary": "Players using media, unions, and free agency to rewrite who captures the league's upside.",
                "volume_percent": 24.0,
                "representative_posts": [
                    {"author": "pod-rights", "text": "The league wants the highlight. The player wants the company. That fight is the modern CBA.", "likes": 877},
                    {"author": "nil-era", "text": "College stars getting paid is not the scandal. Unpaid billion-dollar broadcasts were the scandal.", "likes": 720},
                    {"author": "locker-room", "text": "Load management is a labor practice. We only call it soft when the labor is famous.", "likes": 401},
                ],
            },
            {
                "id": "9B",
                "title": "Ticket Prices",
                "summary": "Fans treat dynamic pricing as a slow eviction from the building they grew up in.",
                "volume_percent": 22.0,
                "representative_posts": [
                    {"author": "nosebleed", "text": "A Tuesday night and a beer cost what a weekend used to. The sport is on TV because the seats lost.", "likes": 1604},
                    {"author": "transfer-fee", "text": "Service fees larger than the ticket should be illegal in any industry that lectures about community.", "likes": 933},
                    {"author": "family-four", "text": "We do one game a year now. The rest is streams and highlights. That is not a fanbase, that is a funnel.", "likes": 512},
                ],
            },
            {
                "id": "9C",
                "title": "Media Rights",
                "summary": "Blackouts and app-hopping make following a team feel like a subscription puzzle.",
                "volume_percent": 18.0,
                "representative_posts": [
                    {"author": "blackout-city", "text": "Local team, local market, no legal stream. Piracy is a user-experience review.", "likes": 1401},
                    {"author": "sunday-ticket", "text": "I need three logins to watch one weekend. The product is fragmentation.", "likes": 688},
                    {"author": "radio-still", "text": "The radio call remains the most honest interface left. Nobody upsold me a 4K option mid-drive.", "likes": 290},
                ],
            },
            {
                "id": "9D",
                "title": "Fan Culture",
                "summary": "Supporters talk belonging, away days, and the social life that the broadcast cannot replace.",
                "volume_percent": 16.0,
                "representative_posts": [
                    {"author": "ultras-lite", "text": "The chant is the civic religion that still lets strangers share a throat. That is not branding.", "likes": 540},
                    {"author": "away-end", "text": "Spent more on the train than the seat. Still cheaper than therapy and more honest than a group chat.", "likes": 377},
                    {"author": "footy-pub", "text": "If your club is a content vertical, you already lost the plot. Clubs are places.", "likes": 266},
                ],
            },
            {
                "id": "9E",
                "title": "Betting Boom",
                "summary": "Legal sportsbooks are praised as engagement and blamed as a debt machine beside the scoreboard.",
                "volume_percent": 12.0,
                "representative_posts": [
                    {"author": "odds-push", "text": "The app congratulated me for a $8 parlay and offered me a line of credit. Cute.", "likes": 1011},
                    {"author": "prop-shop", "text": "When every broadcast is an ad for a book, the game is the undercard.", "likes": 602},
                    {"author": "recovering", "text": "I like basketball. I do not like a push notification that knows I am sad after a loss.", "likes": 488},
                ],
            },
            {
                "id": "9F",
                "title": "Youth Sports",
                "summary": "Parents describe travel ball and club fees as a childhood industry with a burnout problem.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "sideline-sat", "text": "We paid four figures for a 10-year-old to stand in the cold. Development or dues? Unclear.", "likes": 733},
                    {"author": "rec-league", "text": "The rec team died. The travel team has a brand. Childhood got a paywall.", "likes": 501},
                    {"author": "coach-volunteer", "text": "I just wanted Saturday mornings. I got a group chat that treats 8-year-olds like prospects.", "likes": 344},
                ],
            },
        ],
    },
    {
        "id": 10,
        "name": "Media Trust",
        "total_volume_percent": 3.3,
        "perspectives": [
            {
                "id": "10A",
                "title": "Platform Bias",
                "summary": "Users treat ranking systems as editors and argue about who the invisible desk is working for.",
                "volume_percent": 28.0,
                "representative_posts": [
                    {"author": "for-you", "text": "I did not subscribe to this rage. The algorithm assigned it like homework.", "likes": 1333},
                    {"author": "reach-drop", "text": "Same links, different week, different reach. If that is not editorial, invent a new word.", "likes": 701},
                    {"author": "reply-guy", "text": "The most amplified take is rarely the most informed. It is the one that keeps you tapping.", "likes": 544},
                ],
            },
            {
                "id": "10B",
                "title": "Local News Collapse",
                "summary": "The empty newsroom is blamed for both corruption and the conspiracy shows that replace it.",
                "volume_percent": 22.0,
                "representative_posts": [
                    {"author": "ghost-paper", "text": "The county lost its daily. The school board now live-streams to 11 people and a lobbyist.", "likes": 980},
                    {"author": "one-reporter", "text": "I cover courts, weather, and the plant. That used to be three jobs. Now it is a newsletter.", "likes": 612},
                    {"author": "paywall-town", "text": "People will not pay. Ads will not pay. Civic information is somehow supposed to be free and excellent.", "likes": 388},
                ],
            },
            {
                "id": "10C",
                "title": "Influencer Politics",
                "summary": "Creators are now the primary interpreters of news for audiences that left the evening desk.",
                "volume_percent": 18.0,
                "representative_posts": [
                    {"author": "stream-desk", "text": "My newsroom is a ring light and a Google Doc. That should scare the old brands more than it does.", "likes": 808},
                    {"author": "clip-economy", "text": "A 40-second outrage pays better than a 2,000-word explainer. We optimized ourselves into this.", "likes": 640},
                    {"author": "comment-show", "text": "I trust the person who shows their work live more than the chyron. That is a design failure, not a moral one.", "likes": 355},
                ],
            },
            {
                "id": "10D",
                "title": "Fact-Check Fatigue",
                "summary": "Corrections arrive late, feel partisan, and sometimes deepen the thing they meant to kill.",
                "volume_percent": 14.0,
                "representative_posts": [
                    {"author": "label-wear", "text": "If every rival story is 'misleading', the word is out of calories.", "likes": 711},
                    {"author": "community-note", "text": "The note was useful. The two-day delay was the actual vector. Speed is a truth problem.", "likes": 490},
                    {"author": "both-sides-pm", "text": "I want methods, not a referee costume. Show me the dataset or sit down.", "likes": 301},
                ],
            },
            {
                "id": "10E",
                "title": "Public Media",
                "summary": "Defenders and critics argue over whether tax-supported news is a commons or a faction.",
                "volume_percent": 10.0,
                "representative_posts": [
                    {"author": "member-drive", "text": "I will fund the show that still sends someone to the zoning hearing. That is the product.", "likes": 455},
                    {"author": "defund-it", "text": "If it needs a pledge week and a federal line, it should withstand a bias audit like anyone else.", "likes": 390},
                    {"author": "rural-signal", "text": "When the commercial tower goes silent, the public transmitter is the last weather report. Remember that.", "likes": 277},
                ],
            },
            {
                "id": "10F",
                "title": "Slow Journalism",
                "summary": "A minority is rebuilding trust with methods sections, corrections, and stories that take a week.",
                "volume_percent": 8.0,
                "representative_posts": [
                    {"author": "methods-first", "text": "I do not need you to be neutral. I need you to be inspectable.", "likes": 866},
                    {"author": "weekender", "text": "The piece that changed my mind was late, long, and boring in the best way. Ship more of those.", "likes": 412},
                    {"author": "corr-log", "text": "A visible corrections file is a stronger brand than a confident anchor.", "likes": 240},
                ],
            },
        ],
    },
]


def build_demo_payload(last_updated: str = DEMO_LAST_UPDATED, total_posts: int = DEMO_TOTAL_POSTS) -> dict[str, Any]:
    """Return a data.json document that matches the UI canvas schema."""
    topics = [{**topic, "category": DEMO_CATEGORIES[topic["id"]]} for topic in DEMO_TOPICS]
    payload = {
        "last_updated": last_updated,
        "total_posts": total_posts,
        "window_hours": 168,
        "source": "synthetic",
        "mode": "demo",
        "noise_policy": NOISE_POLICY,
        "topics": topics,
    }
    validate_payload(payload)
    return payload


def default_output_path() -> Path:
    return Path(__file__).resolve().parent.parent / "public" / "data.json"


def write_demo_data(output_path: Path | None = None) -> Path:
    path = Path(output_path) if output_path else default_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_demo_payload()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the Perspectiverse demo data.json")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Destination path (defaults to public/data.json)",
    )
    args = parser.parse_args()
    path = write_demo_data(args.output)
    print(f"Wrote demo universe to {path}")


if __name__ == "__main__":
    main()
