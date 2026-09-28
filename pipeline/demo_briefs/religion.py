"""Religion extras."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Church and State": faces(
        (
            "School Prayer",
            "The old fight in a new costume: staff-led devotion, student clubs, and a board that wants a script.",
            (
                "A teacher with a captive room is not a student club. The captive is the constitutional fact.",
                "If the board writes the prayer, it is a government speech. Stop calling it a vibe of the kids.",
                "Equal access for student groups is the boring peace. A preferred script is the war.",
            ),
            (
                ("captive", "My kid cannot leave math. Do not put a devotion in math. Clubs are after the bell."),
                ("board-script", "They drafted a prayer in a work session. That is not grassroots. That is a legislature."),
                ("equal-access", "Let the kids meet. Do not pick the meeting. I can live with that truce."),
            ),
        ),
        (
            "Tax Status",
            "501(c)(3) as a bargain: no electioneering, a pulpit, and a donation that is a public subsidy.",
            (
                "A deduction is a spend. If the pulpit is a PAC, the spend is a campaign finance story.",
                "Houses that are mostly parking lots and political mail are testing the bargain on purpose.",
                "Revoking is rare. Reporting is rarer. The bargain needs a cop or it is a story we tell.",
            ),
            (
                ("the-spend", "I deduct the gift. You do a slate. That is a public financing program."),
                ("parking-lot", "The sanctuary is a room. The operation is a mailer. Audit the mailer."),
                ("a-cop", "Nobody is the cop. So the bargain is a rumor. I would like a rumor with a form."),
            ),
        ),
        (
            "Hospitals",
            "Conscience clauses in the only ER for 80 miles — doctrine as a formulary.",
            (
                "A public that funds the building should know which care will not happen at 2am.",
                "If the merger made the Catholic the only shop, the merger is the statute.",
                "Clinicians who cannot follow a legal protocol because of a sponsor are practicing under two licenses.",
            ),
            (
                ("2am", "The ER is a ministry and a monopoly. I found out in the hallway. Put it on the sign."),
                ("merger", "They bought the secular one and kept the rule. That is how a doctrine becomes a county."),
                ("two-licenses", "The state said I could. The sponsor said I could not. The patient heard the sponsor."),
            ),
        ),
        (
            "Monuments",
            "The lawn, the cross, the Ten Commandments as a test: history, or a current majority's brand.",
            (
                "A monument that only appears when one faction has the gavel is not heritage. It is a win.",
                "Context that is a plaque nobody reads is how you keep a fight forever.",
                "If other groups cannot put a stone next to it, it is a preference, not a museum.",
            ),
            (
                ("the-gavel", "They installed it in a good year. Heritage usually takes longer than a term."),
                ("plaque", "The plaque says history. The rally says ours. I believe the rally."),
                ("next-stone", "Let the others add a stone or admit it is a brand. I can live with a brand that tells the truth."),
            ),
        ),
    ),
    "Youth Faith": faces(
        (
            "Nones",
            "The rise of nothing-in-particular: not a manifesto, a shrug, and a holiday that is now just a meal.",
            (
                "A shrug is not a philosophy. It is also the largest youth 'tradition' in some counties. Plan for the shrug.",
                "If belonging left before belief did, the product to rebuild is the room, not the argument.",
                "Polling that treats 'none' as atheist will miss the astrology, the grief, and the leftover God.",
            ),
            (
                ("shrug", "I did not deconvert. I just stopped. There was no scene. There was a Sunday."),
                ("the-room", "I miss the people. I do not miss the votes. Build a people without the votes."),
                ("leftover", "I still say a thing at graves. The survey called me a none. The grave did not."),
            ),
        ),
        (
            "Campus Groups",
            "InterVarsity, Hillel, MSA: a table in a quad that is still a pipeline, and a fight over who may lead.",
            (
                "A group that requires a doctrine of its leaders is a church on a lease. The lease is the fight.",
                "If the campus can host everyone except the unpopular orthodox, it is a preference with a dean.",
                "Students still convert, still leave, still eat. The table is doing more than the thread.",
            ),
            (
                ("lease", "They wanted a leader who signs a statement. The university wanted a nondiscrimination form. Both are serious."),
                ("unpopular", "The group I hate still gets a table. That is the whole idea. I can hate them at the table."),
                ("eat", "We ate. We argued. Nobody ratioed anybody. Ancient technology."),
            ),
        ),
        (
            "TikTok",
            "A new catechism in 30 seconds: aesthetics, testimony, and a priest who is an algorithm.",
            (
                "A faith that only lives in a feed will take the feed's incentives: conflict, glow, a product.",
                "Testimony as content is old. The metric is new. The metric will shape the testimony.",
                "If the only catechesis is a creator, the creator is a bishop. Ask who ordained them.",
            ),
            (
                ("glow", "My For You is a monastery with ring lights. I can feel the sell."),
                ("metric-testimony", "She cried on beat. I believed her and also the edit. That is the sacrament now."),
                ("who-ordained", "He has 2 million. That is the ordination. I would like a second opinion."),
            ),
        ),
        (
            "Parents",
            "Households trying to pass something down without a war: a meal, a practice, a kid who has questions and a phone.",
            (
                "A faith that cannot survive a question at 14 will not survive a campus at 18.",
                "Forcing a performance of belief is how you get a quiet none at 22.",
                "If the only time God is discussed is a culture-war clip, the kid will think God is a clip.",
            ),
            (
                ("questions", "She asked. I did not panic. That is the whole strategy."),
                ("performance", "I made him pretend. He is very good at pretending. He is also gone."),
                ("clip-god", "We watched a pastor dunk on a stranger. Then we wondered why she thinks this is mean."),
            ),
        ),
    ),
    "Religious Freedom": faces(
        (
            "Exemptions",
            "The clause as a shield: vaccines, cakes, and a test that keeps moving with the coalition.",
            (
                "A shield that only one coalition can pick up is a privilege. Call it a privilege.",
                "If the harm lands on a third party — a patient, a worker — the exemption needs a narrower needle.",
                "Sincerity tests are ugly. So is a factory of sudden beliefs that track the news.",
            ),
            (
                ("one-coalition", "When they needed an exemption it was liberty. When we needed one it was a loophole. I kept the clips."),
                ("third-party", "Your conscience is yours. My shift is mine. Do not conscript my body into your clause."),
                ("sudden", "The belief arrived with the headline. I can respect an old one. I side-eye a new one."),
            ),
        ),
        (
            "Workplaces",
            "Sabbath, hijab, a beard, a schedule — accommodations that are easy until they are not.",
            (
                "A schedule that cannot bend for a Friday prayer will also not bend for a kid. It is a boss problem.",
                "Grooming rules that invent a sudden neutrality are often a preference with a handbook.",
                "If the customer is the excuse, the customer is a veto the firm chose to honor.",
            ),
            (
                ("friday", "I can work a long Thursday. I cannot invent a second noon. Meet me in the middle."),
                ("handbook", "The beard was fine until a new VP. Neutrality is a person."),
                ("customer-veto", "They hid behind a complaint. They could have hidden behind me. They picked."),
            ),
        ),
        (
            "Minorities",
            "The clause as it actually arrives for a mosque, a Sikh, a small church that is not in the coalition.",
            (
                "A freedom that is loud for the majority and quiet for the storefront mosque is a brand, not a doctrine.",
                "Zoning that discovers 'traffic' when the applicant is the wrong holy day is the tell.",
                "If the legal-aid is only on one side, the freedom will look like that side.",
            ),
            (
                ("storefront", "We are a church on paper. We are a problem at the hearing. I noticed the difference."),
                ("traffic", "The gym was fine. Our Eid was a crisis. Traffic had a religion."),
                ("legal-aid", "They have a firm. We have a group chat. That is the playing field."),
            ),
        ),
        (
            "Courts",
            "Tests, tiers, and a doctrine that is in motion — Smith, RFRA, a shadow of both.",
            (
                "A test that changes with the bench is hard to live inside. People need a rule they can calendar.",
                "RFRA as a sword against generally applicable law is a different statute than the shield people voted for.",
                "If every case is a culture-war vehicle, the doctrine will be a vehicle. Ask whether you wanted a vehicle.",
            ),
            (
                ("calendar", "Tell me if I can close on Saturday. Do not tell me a theory. I have a lock to buy."),
                ("sword", "I voted for a shield. They bought a sword. I can read the difference in the caption."),
                ("vehicle", "The case is a bus. The facts are a tourist. I miss cases that were about the facts."),
            ),
        ),
    ),
    "Clergy Abuse": faces(
        (
            "Records",
            "The file: who knew, which drawer, a statute of limitations that ran while the drawer stayed shut.",
            (
                "A secret archive is not pastoral care. It is evidence control.",
                "If the names only move when a state forces a list, the institution is not the first mover. Credit the force.",
                "Limitations that expire while the file is hidden are a design, not an accident.",
            ),
            (
                ("drawer", "They had a list. They had a lawyer. They did not have a Tuesday for us."),
                ("the-force", "Do not praise the release. Praise the subpoena."),
                ("design", "The clock ran. The drawer did not. That is not time. That is a strategy."),
            ),
        ),
        (
            "Settlements",
            "Money as the only remaining sacrament some survivors will accept — and a confidentiality that buys quiet.",
            (
                "A check that requires silence is a second injury with a wire.",
                "Bankruptcy that names the victims as creditors is a legal truth and a moral grotesque. Hold both.",
                "If the insurance wrote the apology, the apology will read like an insurance memo.",
            ),
            (
                ("silence", "They paid me to go quiet. I took the rent. I did not take the peace."),
                ("creditors", "We are a line item in a reorganization. That sentence is the wound and the record."),
                ("memo-sorry", "The letter had a reservation of rights. I wanted a name and a door."),
            ),
        ),
        (
            "Survivors",
            "People who want a process that is not a PR cycle: a seat, a pace, a refusal to be a prop.",
            (
                "A listening session without power is a sedative.",
                "If the story only runs on a round number anniversary, the story is a calendar, not a commitment.",
                "Survivors are not a brand. Using the story to sell a reform you will not staff is a tell.",
            ),
            (
                ("sedative", "They listened. They kept the keys. I slept worse."),
                ("anniversary", "Call me on a random Wednesday. The anniversary is for them."),
                ("staff-it", "The task force is a PDF. I would like a person with a phone and a budget."),
            ),
        ),
        (
            "Reform",
            "Windows, lay review, a mandatory reporter rule that actually reports — institutional design after the fall.",
            (
                "A lay board that cannot fire is a focus group.",
                "Training videos without a hotline that leaves the house are a liability product.",
                "If the same lawyers still run the response, the org chart did not change. The letterhead did.",
            ),
            (
                ("focus-group", "We advised. They thanked. The priest stayed. That is not a board."),
                ("hotline-out", "The number went to the chancery. The chancery is the problem. Send it out of the house."),
                ("letterhead", "New policy, same counsel. I can read an org chart."),
            ),
        ),
    ),
    "Interfaith Cities": faces(
        (
            "Shared Space",
            "A gym, a school gym, a room that rotates a Friday, a Saturday, a Sunday.",
            (
                "A city that cannot share a gym has a theology of real estate, not of God.",
                "If the permit is easy for one calendar and a saga for another, the saga is the policy.",
                "Shared kitchens and washrooms are the unglamorous peace. Fund the unglamorous.",
            ),
            (
                ("gym", "We rotate. Nobody died. The calendar is the miracle."),
                ("saga", "Their carnival is a form. Our Eid is a task force. I filed both."),
                ("sinks", "Put in the sinks the rules need. Doctrine is easier when the plumbing exists."),
            ),
        ),
        (
            "Holidays",
            "The school calendar as a map of who is 'normal': tests on holy days, a tree in the hall, a diet in the cafeteria.",
            (
                "A test on a fast is not neutrality. It is a preference that did not check a calendar.",
                "If the winter concert is a single tradition, say so. Do not call it a seasons medley and then pick one season.",
                "Food is the first interfaith policy most kids meet. Get the food right.",
            ),
            (
                ("fast-test", "She sat a midterm on a fast. The make-up was a rumor. Put it in the handbook."),
                ("one-season", "We sang the one tree. The slide said many. The kids can see."),
                ("cafeteria", "A kosher-halal-veg line is a peace plan. It is also lunch. Do lunch."),
            ),
        ),
        (
            "Safety",
            "Guards, a camera, a bomb threat that is now a liturgical season for some congregations.",
            (
                "A house of worship that needs a volunteer security team is living in a policy failure.",
                "If the grant for cameras is the only federal visit, the visit is not enough.",
                "Threats that the city treats as a PR problem will become a twice-a-year tradition.",
            ),
            (
                ("volunteer-guard", "Our usher has a radio now. That used to be a hymn. I want the hymn back."),
                ("cameras-only", "They funded a lens. I would like a prosecutor who returns a call."),
                ("tradition", "We do this every fall. The city is always surprised. I am not."),
            ),
        ),
        (
            "Food",
            "Halal, kosher, potluck politics: whose dish may enter the room, and a health dept that only knows one kitchen.",
            (
                "A rule that treats one community's meat as a problem and another's as a festival is a ranking.",
                "If the health code cannot imagine a kosher pop-up, rewrite the code, not the people.",
                "Potlucks are foreign policy. Label the dish. Do not police the soul.",
            ),
            (
                ("ranking", "The barbecue is a civic good. The other grill is a hearing. I can taste the ranking."),
                ("pop-up", "Let us cook. Write a permit that knows what a mashgiach is. It is not exotic. It is a job."),
                ("label", "Tell me if there is pork. Do not tell me if I am saved. That is a better city."),
            ),
        ),
    ),
    "Secular Surge": faces(
        (
            "Unbelief",
            "Atheism, agnosticism, and a public life that no longer needs a chaplain to open the meeting.",
            (
                "A city that can start a meeting without a prayer is not hostile. It is plural.",
                "If unbelief is treated as a hole to be filled, the filling will feel like a sale.",
                "Moral language without a sky is already how most people argue. Notice it.",
            ),
            (
                ("no-chaplain", "We had a quorum and a clock. We did not need a guest deity. The vote still counted."),
                ("a-sale", "They keep offering me a hole. I have a life. The life is the point."),
                ("already", "We already say ought without a citation. The citation was optional. I opted out."),
            ),
        ),
        (
            "Ritual Lite",
            "Sunday assemblies without a creed: humanist halls, solstice, a funeral that is still a funeral.",
            (
                "People still need a script for death and a baby. The market will provide a script. Ask who writes it.",
                "A ritual that is only an aesthetic will lose to one that can hold a body.",
                "Borrowing the music and skipping the metaphysics is allowed. It is also unstable. Be honest about the borrow.",
            ),
            (
                ("the-script", "We needed words at the grave. The off-the-shelf ones were fine. I still want better writers."),
                ("hold-a-body", "Candles are pretty. A community that brings casseroles is the ritual."),
                ("borrow", "We sang their song. We did not pay their tithe. I can live with the debt if we name it."),
            ),
        ),
        (
            "Politics",
            "Nones as a bloc that does not act like a bloc — and a party that is unsure whether to court or fear them.",
            (
                "A secular vote that only exists as 'not that' will be rented by whoever is not that this year.",
                "If the left treats churches as a museum of the enemy, it will miss the mutual-aid ones.",
                "Public reason is a discipline. Mocking it as cringe is how you get a politics of vibes.",
            ),
            (
                ("rented", "I voted against a slate, not for a catechism. Do not baptize me in the victory speech."),
                ("mutual-aid", "The church van still shows up. The meme does not. I can hold that without converting."),
                ("cringe", "Give me a reason that works on a stranger. The inside joke is not a coalition."),
            ),
        ),
        (
            "Community",
            "The hole after leaving: friends, childcare, a Tuesday, a death — the unglamorous utilities of a congregation.",
            (
                "If your secular life cannot find a casserole, you did not replace the church. You replaced the sermon.",
                "Third places that are not a bar are the actual religious-freedom issue for the unaffiliated.",
                "Parenting without a parish is logistics. Build the logistics or stop wondering why people go back.",
            ),
            (
                ("casserole", "When he died, the group chat sent hearts. The parish would have sent a dish. I noticed."),
                ("not-a-bar", "I would like a Tuesday that is not alcohol. Libraries almost count. Fund more almosts."),
                ("logistics", "I went back for the nursery, not the creed. That is an indictment of the rest of us."),
            ),
        ),
    ),
    "Mutual Aid Faith": faces(
        (
            "Shelters",
            "Congregations as the overnight floor the city still calls emergency — mats, a rota, a zoning fight.",
            (
                "A sanctuary that is a shelter is doing the state's job at a tithe rate.",
                "If the city will not zone a clinic but will praise a church basement, the praise is the policy.",
                "Burnout in the rota is a staffing story. Volunteers are not a renewable resource just because they pray.",
            ),
            (
                ("tithe-rate", "We are the overflow. The overflow is a department. Pay like a department or stop sending vans."),
                ("praise", "They clapped at the breakfast. They denied the permit. I kept the clap for the minutes."),
                ("rota", "Same twelve people. Faith is not a headcount. Hire the thirteenth."),
            ),
        ),
        (
            "Food Banks",
            "The pantry as the real safety net: a box, a line, a doctrine that may or may not come with the rice.",
            (
                "A pantry that requires a sermon is a trade. Say the trade at the door.",
                "If SNAP is a cliff and the church is the floor, the church is a USDA with hymns.",
                "Supply that is last week's bread is still calories. It is also a story about the rest of the system.",
            ),
            (
                ("the-trade", "I will take the rice. I will not take the altar call. Put that on the sign or I will."),
                ("usda-hymns", "We are doing the state's calories. I would like the state's trucks."),
                ("bread", "It is still food. It is also a monument to a gap. I can hold a can and a complaint."),
            ),
        ),
        (
            "Disaster",
            "The van that arrives before FEMA: chainsaws, a kitchen, a chaplain who also has a generator.",
            (
                "Mutual aid that beats the org chart is a compliment and an indictment.",
                "If the only bilingual team is the church, the county has a language policy problem.",
                "Clergy who do logistics should be in the EOC, not as mascots, as operators.",
            ),
            (
                ("chainsaw", "We had fuel. They had a presser. Fuel won Tuesday."),
                ("bilingual", "Our youth group did intake in two languages. The county had a form in one. Fix the form."),
                ("eoc", "Put us in the room. We already have the list of who has a generator."),
            ),
        ),
        (
            "Volunteers",
            "The same retired people, a youth group, a liability form — the labor model of a thousand 501(c)(3)s.",
            (
                "A model that depends on a 70-year-old's back is a clock.",
                "Youth missions that are a photo are not a labor force. They are a brochure.",
                "If you want reliability, mix the rota with a wage. Holiness will not cover Thursday forever.",
            ),
            (
                ("clock", "Our best volunteer is 74. That is a miracle and a warning."),
                ("photo", "They came for a reel. We needed a driver in February. Hire a driver."),
                ("thursday", "Pay one coordinator. I will keep the miracle. I will not pretend the miracle is a plan."),
            ),
        ),
    ),
    "Ritual Online": faces(
        (
            "Livestreams",
            "The sanctuary as a camera: a gift for the homebound and a habit for the rest.",
            (
                "A stream that replaces the room will eventually replace the pledge, the casserole, and the argument.",
                "If the homebound are the reason, design for them — captions, a call, a person who notices an empty square.",
                "Multi-site churches that are a brand with a lens already made this choice. The rest are sliding into it.",
            ),
            (
                ("replace", "We kept the stream after we could go back. The room got polite and thin."),
                ("square", "Caption it. Call the person who always watched and then did not. That is pastoral care."),
                ("brand-lens", "The pastor is a thumbnail. I miss a person who knows my kid's name."),
            ),
        ),
        (
            "Apps",
            "Prayer as a streak: notifications, a paywall on a psalm, a community that is a server.",
            (
                "A streak is a slot machine. Holiness that needs a streak will take the slot's ethics.",
                "If the psalm is behind a subscription, you have made a utility into a SaaS.",
                "Push notifications at 6am are a discipline some people want. They are also a product.",
            ),
            (
                ("streak", "I prayed because the flame would die. That is not what I meant by daily."),
                ("saas-psalm", "The text is older than the store. Charge me for the community, not the text."),
                ("6am", "The bell is fine. The upsell after the bell is why I deleted it."),
            ),
        ),
        (
            "Grief",
            "Funerals on a laptop, a guest book that is a comments field, a death that will not sit still on a feed.",
            (
                "A stream of a funeral is a mercy for the cousin who cannot fly. It is a theft if it becomes content.",
                "Comments under a death are a new etiquette we are bad at. Write a rule.",
                "If the only shiva is a group chat, someone still has to bring the real dish. The chat will not.",
            ),
            (
                ("mercy-theft", "Aunt Jane saw it. A stranger also did. One of those was the point."),
                ("etiquette", "Do not like a death. Do not ratio a widow. We need a book of manners for this site."),
                ("real-dish", "The chat was kind. The lasagna still had to exist. I drove the lasagna."),
            ),
        ),
        (
            "Attention",
            "The feed as a rival liturgy: hour for hour, a Sabbath that has to be a setting.",
            (
                "A practice that cannot survive a phone in the pew already lost to a better ritual designer.",
                "Sabbath as airplane mode is a joke that is also a rule. Keep the rule.",
                "If the sermon has to compete with a clip, shorten the sermon or improve the silence. Do not just add lights.",
            ),
            (
                ("better-designer", "They have a thousand engineers. We have a bulletin. I know who is winning the hour."),
                ("airplane", "On Saturday the phone dies in a bowl. That is the most religious thing I do."),
                ("silence", "Do not add a screen. Subtract a noise. I came for a room that does not ping."),
            ),
        ),
    ),
    "Sacred Land": faces(
        (
            "Burial Sites",
            "Bones, a survey, a project that discovered a cemetery in a trench.",
            (
                "A site that is a cemetery is not a surprise if you asked the people who bury.",
                "If the law requires a halt, the halt is the point. Speed is the vandalism.",
                "Reburial that is a ceremony and not a PR is the only adult ending.",
            ),
            (
                ("asked", "We told them in the hearing. They found us in the trench. Listening is cheaper."),
                ("halt", "Stop the machine. The schedule is not a sacrament."),
                ("not-pr", "Bring the families. Leave the cameras. Do the work."),
            ),
        ),
        (
            "Pipelines",
            "Routes, easements, water, a prayer that is also a blockade.",
            (
                "A route that only gets easy when it is on someone else's treaty is not engineering. It is a map of power.",
                "Consultation after the PEA is a courtesy. Consent is a veto they do not want to write.",
                "Water as a relative is a legal theory in some places and a metaphor in others. Know which jurisdiction you are in.",
            ),
            (
                ("treaty-easy", "The other side of the river was harder. Wonder why."),
                ("courtesy", "They mailed us the plan. The plan had a start date. That is not a question."),
                ("jurisdiction", "Here the water is a person. Your metaphor can wait in the truck."),
            ),
        ),
        (
            "Parks",
            "Public land that is also a shrine: climbing bans, a solstice, a ranger in the middle.",
            (
                "A park that cannot hold a closed day for a ceremony is a recreation product, not a commons with a memory.",
                "If climbers and a nation both love a rock, the law has to rank. Pretending it will not rank is how you get a surprise closure.",
                "Rangers as cops of the sacred is a job nobody trained them for. Write the protocol.",
            ),
            (
                ("closed-day", "Give the morning to the people who named it. The afternoon can be a postcard."),
                ("rank", "Say the ranking in the plan. I can hate it in daylight."),
                ("protocol", "Do not make a GS-7 invent a theology at a trailhead. Send a letter."),
            ),
        ),
        (
            "Repatriation",
            "Museums, NAGPRA, a drawer of remains that was a collection and is a relative.",
            (
                "A catalog number is not a name. The work is the name.",
                "If the museum's identity requires the drawer, the identity is the problem.",
                "Speed without care is a second taking. Care without speed is a stall. Staff both.",
            ),
            (
                ("the-name", "Give them back with a name if you have it. The number can stay in your shame file."),
                ("identity", "We can be a museum without a basement of people. Try. It is allowed."),
                ("staff-both", "Hire the team. Date the boxes. Do not make a nation wait on an intern year."),
            ),
        ),
    ),
    "Evangelical Politics": faces(
        (
            "Primary Voters",
            "A bloc that still decides a Tuesday in some states — pastors, a text list, a candidate in the foyer.",
            (
                "A foyer that is a precinct is legal. It is also a party. Put the disclaimer where the coffee is.",
                "If the bloc can punish a heresy faster than a legislature, the heresy is the whip.",
                "Turnout operations that are 'just church' are why people who are not in the church feel like a minority in a majority county.",
            ),
            (
                ("coffee", "The sample ballot was next to the donuts. I can read a precinct when I see one."),
                ("whip", "They moved faster than the party. The party noticed. So did I."),
                ("minority-feel", "I live here. I do not go there. On Tuesday it feels like their house. That is data."),
            ),
        ),
        (
            "Media",
            "A parallel news: radio, a network, a phone that never shows the other graph.",
            (
                "A media that cannot survive a contrary fact will eventually try to survive by calling the fact a persecution.",
                "If the only journalists in the coalition are advocates, the coalition will not see the crash coming.",
                "Crossover that is only a hostage video of a 'liberal' is not information. It is a rite.",
            ),
            (
                ("persecution", "The number was the number. They called it a plot. I kept the number."),
                ("crash", "Nobody in the feed does courts. Then the court arrived. Surprise is expensive."),
                ("rite", "I watched a ritual of dunking. I did not watch a story. Name it a ritual."),
            ),
        ),
        (
            "Young Exit",
            "The quiet leaving: not always deconstruction-as-content, sometimes a job, a gay cousin, a tiredness.",
            (
                "A politics that needs the young and scolds the young will get neither.",
                "If the only story of leaving is a traitor narrative, you will not hear why they left.",
                "Exvangelical as a brand is real. So is a kid who just wanted a church that could lose a race without a prophecy.",
            ),
            (
                ("scold", "They wanted my vote and my silence. I kept the vote to myself."),
                ("traitor", "Ask me why. Do not start with a demon. I left because of a cousin and a vote."),
                ("lose-a-race", "I wanted a sermon that could survive November. We got a weather report. I changed rooms."),
            ),
        ),
        (
            "Policy",
            "The actual asks: judges, schools, a rule about bodies — a program, not a vibe.",
            (
                "A movement that cannot name a health-care plan but can name a court is a judicial project. Describe it that way.",
                "Schools are the domestic policy. Everything else is a poster.",
                "If the program requires a state small enough to drown except where it touches a classroom, that is not small. It is selective.",
            ),
            (
                ("judicial-project", "Tell me the clinic plan. You told me the judge. I wrote that down."),
                ("classroom", "The bill is always the school. The rest is a parade."),
                ("selective", "Drown it except the principal's office. That is a big state in a costume."),
            ),
        ),
    ),
}
