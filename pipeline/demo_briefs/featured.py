"""Core arguments for the hand-written featured planets."""

from __future__ import annotations

FEATURED_ARGUMENTS: dict[str, dict[str, list[str]]] = {
    "AI Futures": {
        "Job Displacement": [
            "White-collar work that is mostly drafting, summarizing, or first-pass analysis is already being treated as a cost center, not a craft.",
            "Telling new graduates to become 'AI-proof' is not a labor market. It is an admission that employers will not invest in juniors.",
            "The threat is not a single AGI event. It is a quiet payroll strategy repeating across agencies and back offices.",
        ],
        "Acceleration Optimism": [
            "A free research assistant for a billion people is a moral story about scale, not just a product launch.",
            "Open weights are a literacy shock. The panic rhymes with every other time a tool escaped the guild.",
            "Shipping in a weekend what used to take a squad is the evidence. Feelings are the lagging indicator.",
        ],
        "Safety Alignment": [
            "Capability demos without public evals are fundraising, not governance.",
            "If you cannot measure refusal, you do not have alignment. You have a vibe check with a press kit.",
            "The news is the gap between what the model will do next quarter and what anyone is willing to publish.",
        ],
        "Creative Labor": [
            "A style that shows up in six commercial models without consent is inventory, not inspiration.",
            "Labels and clients still want a human face for the encore while they automate the catalog that paid for it.",
            "'Make this not look generated' is the new commission: unpaid training, then paid cleanup.",
        ],
        "Energy Footprint": [
            "The next substation in town is being sized for a training campus, not households, and that is a public meeting.",
            "Tokens are not a unit of accountability. Megawatts and water are.",
            "Water-cooled racks in a drought basin make AI a utilities story before it is a software story.",
        ],
        "Everyday Copilots": [
            "Most people are not arguing about AGI. They are using a draft to finish the insurance appeal they had been avoiding.",
            "The useful part of homework help is the questions, not the paragraphs.",
            "Imperfect translation of after-visit notes still beats sending someone home confused.",
        ],
    },
    "Housing Costs": {
        "Rent Burden": [
            "When half of take-home pay is a one-bedroom that failed inspection, the market is a policy, not weather.",
            "A graduate degree and three roommates at 34 is not a lifestyle. It is a rationing system with a lease.",
            "Moving an hour out to afford a studio just converts rent into a last-train lifestyle.",
        ],
        "Zoning Reform": [
            "Legalizing duplexes and then inventing new ways to ban them is how shortage becomes a local brand.",
            "A train stop surrounded by lawns is a choice encoded in parking minimums and hearing-room vetoes.",
            "'Neighborhood character' is doing the work of a zoning code that keeps lots empty on purpose.",
        ],
        "Homeownership Gap": [
            "Down payments and insurance quotes are a locked door, not a delayed ladder.",
            "Two incomes and a side gig still cannot match the preapproval one income used to buy.",
            "Starter homes are investment products. Families are bidding against someone's portfolio allocation.",
        ],
        "Investor Landlords": [
            "When twelve units on a street go to an LLC, shelter has been converted into a yield strategy.",
            "A hallway of key-lock boxes is not a neighborhood. It is short-term rental infrastructure.",
            "A chatbot portal cannot own a plunger. Private equity is allergic to maintenance that does not hit a dashboard.",
        ],
        "Construction Costs": [
            "Lumber calmed down. Insurance and interest did not. That is why the mid-rise died at the drawing set.",
            "Eighteen months to approve a four-story building is housing policy, voted on or not.",
            "Four-year degrees will not frame a city. The missing pipeline is trades, not a labor myth.",
        ],
        "Remote Relocate": [
            "Leaving the coast kept the job and cheapened the rent. It also thinned the life that made the job make sense.",
            "Hybrid yanked the arbitrage back. Two office days a week and the math no longer closes.",
            "Every cheap city that got famous in a newsletter is now pricing like it read the same one.",
        ],
    },
    "Climate Policy": {
        "Extreme Weather": [
            "Kids who can identify AQI colors before state birds are living the report, not reading it.",
            "A third flood in five years makes FEMA a form, not a plan.",
            "Nights that do not cool are the new definition of a lucky summer, and that is doing more persuading than any abstract.",
        ],
        "Adaptation Funding": [
            "A net-zero resolution is an afternoon. A cooling center is a line item and a fight.",
            "Retreat is a planning word. On the ground it is buyouts, arguments, and people who will not leave.",
            "When the county map is late, neighbors become infrastructure, and that should embarrass someone paid.",
        ],
        "Fossil Phaseout": [
            "A new terminal is a 40-year bet that the math is optional, not a transition.",
            "If the pension still underwrites expansion, the beach postcard is paid for twice.",
            "Flaring that looks like a city at night is wasted gas plus a permission structure.",
        ],
        "Green Jobs": [
            "Labor will install the transition. It will not applaud a tax credit that skips the union hall.",
            "EV retooling is real. The question is who keeps the pension when the badge changes.",
            "Heat-pump techs booked eight weeks out is demand. Train people like you mean it.",
        ],
        "Climate Delay": [
            "Believing the atmosphere does not require believing every subsidy is a climate policy.",
            "Shut the plant before the replacement exists and you have exported the smoke, not decarbonized.",
            "A coalition that has been two years from breakthrough since school should expect an eye roll.",
        ],
        "Nuclear Debate": [
            "If the climate plan needs weather to cooperate, it is a hope, not a grid.",
            "Closing a working reactor and firing up gas is not a newsletter win.",
            "Waste is a serious risk. So is cooking the rivers. Rank them like an engineer.",
        ],
    },
    "Public Health": {
        "Access Barriers": [
            "Six months for a primary-care intake is a lottery with copays, not a system.",
            "An insurance card that every nearby clinic will not honor is a brochure.",
            "The shortage is beds, nurses, and anyone who can stay past year three — not compassion.",
        ],
        "Drug Pricing": [
            "A coupon that expires while the molecule stays the same is not a market. It is a trapdoor.",
            "Pharmacy techs spending half the day hunting fills people already paid to theoretically have is the real clinical time.",
            "A celebrity-drug shortage crowding out thyroid meds is a priority, not an accident.",
        ],
        "Mental Health": [
            "A kind hotline and a 14-week intake is kindness without capacity.",
            "Seven hundred students and a closet office is the youth mental-health plan in one sentence.",
            "Destigmatizing therapy and then pricing it as a luxury good is a strategy with a punchline.",
        ],
        "Insurance Maze": [
            "Prior auth is the actual clinical bottleneck: a stranger deciding the scan is educational.",
            "Nurses who now speak 'appeals' did not sit for the boards to become billing clerks.",
            "In-network surgeons with surprise anesthesiologists are a plot twist this country refuses to write out of the contract.",
        ],
        "Rural Hospitals": [
            "Labor and delivery 90 minutes away is a policy outcome with a county name on it.",
            "Keeping the highway after losing the hospital is how 2am becomes a distance problem first.",
            "Specialists who fly in twice a month cannot keep a chronic-illness calendar.",
        ],
        "Wellness Culture": [
            "A 12-minute PCP visit loses, on vibes, to a spreadsheet of 40 biomarkers — and that feeling is the product.",
            "Distrust of the food pyramid and of the podcast that replaced it is the whole genre.",
            "A watch that thinks you are thriving is not more honest than bloodwork.",
        ],
    },
    "Labor Markets": {
        "Wage Stagnation": [
            "A 4% raise against 9% everything else is a strong year only in the HR deck.",
            "Essential on the window cling and optional on the schedule is not a wage. It is a slogan.",
            "Posted ranges that start below last year's median are a negotiating tactic dressed as a job.",
        ],
        "Union Revival": [
            "Winning the vote just moves the battlefield onto the bargaining calendar.",
            "Flying in consultants the day after a water-and-fan ask is the tell.",
            "A stadium budget and an empty grader payroll is the university's real priorities list.",
        ],
        "Gig Precarity": [
            "Contractor until the algorithm wants a uniform is flexibility with the safety rails removed.",
            "Quest bonuses vanish. Insurance does not. Dead batteries do not care about the slogan.",
            "Tips on vibes and silence are not a wage, no matter what the app calls them.",
        ],
        "Return To Office": [
            "Three badge-in days for meetings that are still on Zoom is a trust fight, not a collaboration plan.",
            "The commute is a pay cut that does not appear on the offer letter.",
            "Hallway corrections are real. Surveillance is not the same thing as presence.",
        ],
        "Skills Gap": [
            "Five years of experience for a three-year-old tool is a fiction both sides act in.",
            "Hire a human and spend six months teaching the stack. Unicorns are a budget choice.",
            "An ATS that rejects the internal candidate is a maze complaining it is empty.",
        ],
        "Automation Spillover": [
            "A scanner that says you are 12% behind a number nobody can explain is the new supervisor.",
            "Automating the easy cases and leaving humans the screaming ones is efficiency for the dashboard, not the floor.",
            "Models that review the reviewer's time are a funhouse mirror with KPIs.",
        ],
    },
    "Border Policy": {
        "Asylum Backlog": [
            "A hearing date in 2029 is a waiting room with no chairs, not due process.",
            "Running out of mats before families is the backlog with an address.",
            "Allowed to stay and forbidden to earn is a trap built out of processing holes.",
        ],
        "Labor Shortage": [
            "Fruit does not wait for a visa category. You pick it or you import it already picked.",
            "Raising kitchen wages cannot summon a line cook from a closed legal channel.",
            "Aging towns need hands now. Patients cannot postpone while the debate finds a slogan.",
        ],
        "Border Enforcement": [
            "If the rule is optional at the line, it is optional everywhere — that is arithmetic before it is culture war.",
            "Towns that were never ports of entry became them by neglect, without the budget for the plot twist.",
            "Humanitarian language without a queue produces neither humanity nor a line.",
        ],
        "Community Strain": [
            "Four hundred new students and a budget that did not get the letter is a school-board fact, not a slogan.",
            "Compassion without reimbursement is a city credit card.",
            "Hotels as housing is an emergency move that calcified. Emergencies are supposed to end.",
        ],
        "Family Reunification": [
            "A file 'in process' since a nephew learned to walk is a life sentence made of paperwork.",
            "Marriage is legal. The appointment calendar is the actual immigration system.",
            "A degree, a job, and a renewal ritual is not permanence. Permanence should not be a PDF.",
        ],
        "Refugee Welcome": [
            "A spare room and a legal pathway should not feel rare.",
            "Welcome is logistics: rent, language, a dentist. Speeches are the cheap part.",
            "Hosted families on payrolls never get the follow-up episode the scare stories get.",
        ],
    },
    "Digital Privacy": {
        "Surveillance Ads": [
            "Mention a crib once and the feed grows a registry. That is a dossier, not a coincidence.",
            "A privacy dashboard with 40 toggles and one business model is not a choice.",
            "When the billboard knows the cart, public space is just another ad slot.",
        ],
        "Data Brokers": [
            "Paying to be deleted from 80 sites that come back in a month is not a right. It is whack-a-mole.",
            "Selling 'sensitive location' pings is a confession in the category name.",
            "A home address that became a SKU without being listed is a hidden market, not a public record.",
        ],
        "Device Lock-in": [
            "A phone that refuses a $20 battery is a rental with extra steps.",
            "If you cannot install software you trust, you own a showroom, not a computer.",
            "Lose the account and the hardware is a paperweight. Ownership that expires at login is the product.",
        ],
        "Encryption Rights": [
            "A backdoor for the good guys is a front door for everyone else. Math does not do nationalities.",
            "Journalists, clinics, and shelters need the same cryptography as hobbyists. That is the point.",
            "Scan-on-device is still a surveillance architecture no matter how many times it is renamed.",
        ],
        "Kids Online": [
            "The app is free because a 12-year-old is the inventory. That sentence belongs in onboarding.",
            "District-issued devices that are also trackers make homework a telemetry event.",
            "A checkbox that says 'I am 18' is a liability fig leaf, not a child-safety program.",
        ],
        "Open Source Hope": [
            "Moving photos off the big cloud makes you the unreliable vendor, but at least you are not the product.",
            "The boring tools are the freedom tools. Nobody influencers a calendar you can grep.",
            "A model on the desk cannot quietly update its privacy policy at 3am. That is a feature.",
        ],
    },
    "Education Reform": {
        "Student Debt": [
            "Eleven years of payments that leave the principal waving hello is a subscription, not a loan.",
            "Parent PLUS balances make the family spreadsheet the actual diploma.",
            "Skipping the private campus and still drowning in expired certificates is the rest of the market.",
        ],
        "Teacher Pay": [
            "Buying the paper and the snacks and not another year at this wage is the classroom crisis.",
            "Prep period becoming coverage is a staffing model, not a surprise.",
            "Leaving for a district with childcare is recruitment. Housing and pay are pedagogy.",
        ],
        "Curriculum Wars": [
            "Debating a novel while the library loses its clerk is easier than staffing.",
            "Wanting the reading list before the unit starts is a syllabus, not a raid.",
            "Standards that change every election teach the news cycle, not history.",
        ],
        "Childcare Crunch": [
            "Pregnant and 18th on a list means the labor market starts before labor.",
            "The only infant room in town closing turns two careers into one overnight.",
            "Universal pre-k that ends at 2pm is a press conference, not childcare.",
        ],
        "Campus Speech": [
            "A university that cannot hold a disagreement without a lockdown is not a university that week.",
            "Safety is real, and so is the temptation to use safety as a mute button.",
            "No tenure and a viral clip means academic freedom is a feeling reserved for other people.",
        ],
        "Vocational Paths": [
            "Killing the auto shop and then acting shocked that nobody can afford a mechanic is the whole argument.",
            "A two-year nursing program is still the fastest respectable ladder in a lot of towns. Fund it like you mean it.",
            "Out-earning the cousin with the thesis while the guidance office calls it a backup plan is the status trap.",
        ],
    },
    "Sports Culture": {
        "Athlete Power": [
            "The league wants the highlight. The player wants the company. That fight is the modern CBA.",
            "College stars getting paid is not the scandal. Unpaid billion-dollar broadcasts were.",
            "Load management is a labor practice. We only call it soft when the labor is famous.",
        ],
        "Ticket Prices": [
            "A Tuesday night and a beer costing what a weekend used to is a slow eviction from the building.",
            "Service fees larger than the ticket should be illegal in any industry that lectures about community.",
            "One game a year plus streams is not a fanbase. It is a funnel.",
        ],
        "Media Rights": [
            "Local team, local market, no legal stream: piracy is a user-experience review.",
            "Three logins to watch one weekend means the product is fragmentation.",
            "The radio call remains the honest interface. Nobody upsold a 4K option mid-drive.",
        ],
        "Fan Culture": [
            "The chant is civic religion that still lets strangers share a throat. That is not branding.",
            "The train costing more than the seat is still cheaper than therapy and more honest than a group chat.",
            "If the club is a content vertical, the plot is already lost. Clubs are places.",
        ],
        "Betting Boom": [
            "An app that congratulates an $8 parlay and offers a line of credit is a debt machine beside the scoreboard.",
            "When every broadcast is an ad for a book, the game is the undercard.",
            "A push notification that knows you are sad after a loss is not engagement. It is a trap.",
        ],
        "Youth Sports": [
            "Four figures for a 10-year-old to stand in the cold is a childhood industry with a dues problem.",
            "When rec dies and travel has a brand, childhood got a paywall.",
            "A group chat that treats 8-year-olds like prospects is not Saturday morning.",
        ],
    },
    "Media Trust": {
        "Platform Bias": [
            "Ranking systems are editors. The fight is over who the invisible desk is working for.",
            "Same links, different week, different reach — if that is not editorial, invent a new word.",
            "The most amplified take is rarely the most informed. It is the one that keeps you tapping.",
        ],
        "Local News Collapse": [
            "A county without a daily leaves the school board live-streaming to 11 people and a lobbyist.",
            "Courts, weather, and the plant used to be three jobs. Now they are a newsletter.",
            "Civic information is somehow supposed to be free and excellent while people will not pay and ads will not either.",
        ],
        "Influencer Politics": [
            "A ring light and a Google Doc is now a newsroom, and the old brands should be more scared than they are.",
            "A 40-second outrage pays better than a 2,000-word explainer because we optimized ourselves into it.",
            "Trusting the person who shows their work live more than the chyron is a design failure, not a moral one.",
        ],
        "Fact-Check Fatigue": [
            "If every rival story is 'misleading', the word is out of calories.",
            "A useful note two days late is the actual vector. Speed is a truth problem.",
            "Methods beat a referee costume. Show the dataset or sit down.",
        ],
        "Public Media": [
            "The product is still sending someone to the zoning hearing, and that is what a pledge week should buy.",
            "Tax-supported news should withstand a bias audit like anyone else if it wants the federal line.",
            "When the commercial tower goes silent, the public transmitter is the last weather report.",
        ],
        "Slow Journalism": [
            "Neutrality is optional. Inspectability is not.",
            "The piece that changes a mind is late, long, and boring in the best way.",
            "A visible corrections file is a stronger brand than a confident anchor.",
        ],
    },
}
