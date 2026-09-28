"""Politics extras beyond Border Policy."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Voting Access": faces(
        (
            "Early Voting",
            "Election workers and voters treat early and weekend hours as capacity, not a perk — the only way a shift worker casts a legal ballot.",
            (
                "A single Tuesday with a line around the block is not civic virtue. It is understaffing with a flag.",
                "Cutting early days is a turnout strategy that pretends to be administrative hygiene.",
                "If the law requires ID, the law should also require hours a nurse can actually use.",
            ),
            (
                ("night-shift", "I vote at 7am Saturday or I do not vote. That is not a preference. That is a roster."),
                ("line-photo", "Three hours in October heat. They called it enthusiasm. It was a precinct without machines."),
                ("clerk-hours", "Give me poll workers and days. I will give you a shorter line. I cannot give you a shorter week."),
            ),
        ),
        (
            "ID Laws",
            "One cluster wants a photo ID as the boring floor of a high-trust election; another treats the same rule as a poll tax with extra steps.",
            (
                "A free ID that takes a birth certificate you do not have is not free.",
                "People who fly, drive, and bank already live in an ID world. The fight is about the remaining slice, and that slice votes.",
                "If the state can find you for a jury, it can mail a credential. Refusing to is the policy.",
            ),
            (
                ("dmv-bus", "The office is open Tuesdays. The bus does not run Tuesdays. That is the ID law."),
                ("same-id", "I show an ID to pick up a package. I can show one to vote. Stop making it a personality.",),
                ("birth-cert", "She is 78 and her name does not match a 1947 document. The rule found her."),
            ),
        ),
        (
            "Mail Ballots",
            "This view splits between convenience-and-access and chain-of-custody anxiety — both claim to be defending the count.",
            (
                "A ballot that can be intercepted on a kitchen table needs rules that a drop box and a barcode can actually enforce.",
                "Rejecting mail ballots for a missing inner sleeve without a cure process is a quiet purge.",
                "If you want people to trust mail, publish the rejection reasons in real time, not in a PDF in January.",
            ),
            (
                ("cure-form", "My aunt's ballot died for a signature that looks like 80. Nobody called. That is not security. That is a shredder."),
                ("drop-box", "I want a box I can see on a camera and a law that says who may touch it. Both things can be true."),
                ("kitchen-table", "Harvesting is a real word in my county. So is a 12-hour shift. Design for both."),
            ),
        ),
        (
            "Purge Lists",
            "Organizers treat voter-roll maintenance as necessary in theory and a weapon in practice when the notice is a postcard people miss.",
            (
                "Dead people should not vote. Living people should not have to resurrect themselves every two years.",
                "A match that uses a nickname and a county as identity is not maintenance. It is a false positive factory.",
                "The burden of proof belongs on the deletion, not on the 80-year-old who does not refresh her email.",
            ),
            (
                ("postcard", "The notice went to an apartment I left. The deletion went through. Very efficient."),
                ("nickname", "James/Jim is not two people. Your software needs a grown-up."),
                ("poll-book", "She has voted here since 1974. The list decided she moved. The list was sure."),
            ),
        ),
    ),
    "Court Power": faces(
        (
            "Emergency Dockets",
            "Lawyers describe the shadow docket as real policymaking with unsigned orders and no record the public can read.",
            (
                "A nation that is governed by midnight stays is not being governed by opinions. It is being governed by clocks.",
                "If the order will move hospitals and elections, sign it and explain it. Mystery is not a judicial virtue.",
                "Emergency relief that becomes the merits is a cheat code. Everyone in the building knows.",
            ),
            (
                ("unsigned", "The rule of law arrived as a paragraph with no name on it. Forgive the cynicism."),
                ("stay-first", "They stayed the statute, skipped the record, and called it restraint. The clinics closed anyway."),
                ("clocks", "I practice law. Lately I practice time zones. That is the docket."),
            ),
        ),
        (
            "Ethics",
            "This cluster wants a code with teeth — disclosures, recusal, and a body that is not the justices' book club.",
            (
                "A lifetime commission without a binding ethics office is an honor system for people who already won.",
                "Trips and trusts that would torpedo a district judge are not 'appearances' at the top. They are the brand.",
                "Recusal cannot be a vibe. Publish the test and live in it.",
            ),
            (
                ("rv-story", "If a clerk did this, they would be gone. The robe is not a sacrament."),
                ("disclosure", "I file a form for a $50 lunch. They discovered a house in a magazine. Cute symmetry."),
                ("recuse-test", "Write the test down. 'I know it when I don't feel it' is not a standard."),
            ),
        ),
        (
            "State Courts",
            "A quieter thread says the live constitutional law is in statehouses and state benches, not the marble one.",
            (
                "When the federal floor drops, state constitutions become the only roof some people still have.",
                "Electing judges is messy. Pretending they were not already political is messier.",
                "Forum shopping between state and federal is now a basic civic skill. Teach it.",
            ),
            (
                ("state-roof", "Our state constitution still has a sentence the other one lost. That sentence is my clinic."),
                ("retention", "I vote for judges now. I used to think that was for cranks. Then I read a docket."),
                ("two-tracks", "Same facts, two systems. The map is the holding."),
            ),
        ),
        (
            "Precedent",
            "This view treats stare decisis as either a promise to regular people or a slogan the majority uses until it does not.",
            (
                "People plan families, contracts, and agencies on last year's case. Unwinding that is not a seminar. It is a wrecking ball.",
                "A doctrine that was always 'wrong' the day the votes exist was never a doctrine. It was a ceasefire.",
                "Lower courts cannot do their job if the star moves every June.",
            ),
            (
                ("planned-on-it", "We wrote a statute on a case that is now a ghost. Thanks for the stability."),
                ("wrong-then", "If it was always wrong, say what else is. People are taking notes."),
                ("circuit-split", "I cannot advise a client through a vibe. Give me a rule that lasts a fiscal year."),
            ),
        ),
    ),
    "Campaign Money": faces(
        (
            "Dark Money",
            "Watchdogs treat 501(c)(4)s and LLCs as a lighting trick: speech without a nameplate.",
            (
                "A super PAC with a P.O. box is not grassroots. It is a lighting package.",
                "Disclosure that arrives after Election Day is a diary, not a disinfectant.",
                "If a foreign-adjacent LLC can rent an issue ad, the firewall is a PDF.",
            ),
            (
                ("po-box", "The ad loves my kids. The donor loves anonymity. I would like both names on screen."),
                ("post-id", "They disclosed in December. We voted in November. Very brave."),
                ("shell-stack", "Four LLCs deep to a consulting firm that 'does mail'. That is a name. Print it."),
            ),
        ),
        (
            "Small Donors",
            "This cluster still believes a $27 internet haul is a different kind of mandate — and worries platforms now tax that mandate.",
            (
                "Small-dollar is real energy. It is also a rage algorithm with a donate button.",
                "Matching systems can amplify ordinary people without pretending a billionaire match is the same thing.",
                "When the platform takes a cut and the email list is the party, the donor is a subscriber.",
            ),
            (
                ("twenty-seven", "I sent $27 because I was angry at 11pm. That is not a grassroots movement. That is a notification."),
                ("match", "Match the first $50 from residents. Do not match the host of a fundraiser in a penthouse."),
                ("list-rent", "The party is an email vendor. I am the inventory. Cute."),
            ),
        ),
        (
            "PACs",
            "Operatives describe independent expenditure as the campaign that does not have to take the candidate's call.",
            (
                "A candidate who 'cannot coordinate' with the ad that defines them is a legal fiction everyone acts in.",
                "PAC ads go negative because they do not need a smile at the parade.",
                "If the limit is on the check to the campaign, the money will walk around the limit. That is not a puzzle.",
            ),
            (
                ("uncoordinated", "We did not coordinate. We watched the same public polling and had the same consultant cousin."),
                ("neg-buy", "The candidate cuts ribbon. We cut the opponent. Specialization."),
                ("limit-walk", "You capped the hard dollar. Congratulations. The rest bought a holding company."),
            ),
        ),
        (
            "Platform Ads",
            "This view wants political ads treated as political ads: paid labels, targeting limits, and an archive that actually searches.",
            (
                "Microtargeting a lie to 800 people is not speech in the public square. It is a whisper campaign with a pixel.",
                "A library of ads that cannot be queried by targeting criteria is a museum of invoices.",
                "If platforms are scared of being the cop, they can still refuse the scalpel of 'lookalike angry dads in this zip'.",
            ),
            (
                ("800-people", "Nobody else saw the ad. That is the point. The public square has a dark room now."),
                ("ad-lib", "The archive has screenshots and no targeting. It is a scrapbook."),
                ("lookalike", "They bought 'likely to fear crime' in my zip. I would like that sentence in the footer."),
            ),
        ),
    ),
    "Policing": faces(
        (
            "Use of Force",
            "This cluster is still in the footage: when force is justified, who investigates, and why the same zip codes keep the reel.",
            (
                "A policy that cannot survive a cell-phone video was not a policy. It was a hope.",
                "Investigations that start in the same chain of command are why people do not believe the closing memo.",
                "De-escalation is a skill and a staffing number. A memo without training hours is a poster.",
            ),
            (
                ("footage", "I believe in cops. I also believe in the video. Those used to be allowed in the same sentence."),
                ("same-shop", "The squad investigated the squad. The neighborhood took notes."),
                ("hours", "Forty hours of de-escalation and 400 of qualifying. That ratio is the doctrine."),
            ),
        ),
        (
            "City Budgets",
            "Budget fights treat police overtime as the city's uniparty line item — and alternatives as something that never gets a comparable invoice.",
            (
                "If overtime is the staffing model, the overtime is the department. Fund the headcount or stop acting shocked at the number.",
                "Mental-health calls that still roll a cruiser first are an expensive default.",
                "Cutting without a responder for the 2am wellness check is a slogan, not a reallocation.",
            ),
            (
                ("ot-line", "We budgeted for 1,200 and paid for 1,600 in overtime. That is a plan. A bad one."),
                ("wellness-911", "A nurse and a medic should have gone. A gun went. The invoice and the outcome matched."),
                ("reallocate", "Show me the 2am alternative with a radio and a car. Then we can talk about the pie chart."),
            ),
        ),
        (
            "Body Cams",
            "Advocates want footage that actually reaches the public: unedited, timely, and not a FOIA obstacle course.",
            (
                "A camera that is off at the arrival is not a camera. It is a prop.",
                "Release policies measured in months are how departments wait out the news cycle.",
                "If officers review footage before a statement, say that in the policy. Hidden review is a script.",
            ),
            (
                ("off-switch", "The critical two minutes are black. Very convenient hardware."),
                ("foia-maze", "I asked for the tape. They asked for a lawsuit. That is the transparency stack."),
                ("pre-review", "He watched the tape, then remembered. Memory is a special kind of file format."),
            ),
        ),
        (
            "Union Contracts",
            "This view treats the CBA as the real criminal-procedure book: discipline delays, arbitration, and a bill the city cannot reopen.",
            (
                "A contract that resets discipline clocks is how a pattern becomes a personnel file with amnesia.",
                "Arbitrators putting fired officers back on the street is a second electorate nobody voted for.",
                "Negotiate the public parts in public. Mystery clauses are not a labor right.",
            ),
            (
                ("clock-reset", "The complaint aged out. The officer did not. That was the clause."),
                ("arb-back", "The city fired. The arbitrator unfired. The block is the jurisdiction that lost."),
                ("cba-pdf", "The use-of-force policy is a press release. The CBA is the law. Read the CBA."),
            ),
        ),
    ),
    "Foreign Wars": faces(
        (
            "Aid Packages",
            "The live fight is whether weapons and budget support are a cheap defense of an order, or a blank check with no end-state.",
            (
                "Ammunition that keeps a front from collapsing can be cheaper than the world that follows a collapse. That is a real argument.",
                "A package without inspectors and a theory of the end is a mood, not a strategy.",
                "Domestic plants that cannot make 155s are also the story. Aid is an industrial-base test.",
            ),
            (
                ("155-line", "We sent shells we do not make fast enough. That is a factory problem wearing a flag."),
                ("end-state", "I can support a defense. I cannot support a vibe. Write the terms."),
                ("cheap-order", "If the alternative is a bigger war later, the invoice is not the moral fact. The later is."),
            ),
        ),
        (
            "Draft Talk",
            "A nervous cluster treats registration, age, and 'national service' talk as a tell that the volunteer force has a math problem.",
            (
                "People who will not staff an embassy want other people's kids in a queue. Notice that.",
                "A volunteer force that cannot recruit is already a policy. Pretending otherwise is how drafts return as 'reform'.",
                "If the war cannot be explained in a recruiting office, it cannot be explained at a kitchen table.",
            ),
            (
                ("selective", "They said volunteer until the numbers slipped. Then they said civic duty. I heard a queue."),
                ("other-kids", "The op-ed wants a draft. The byline's children are in finance. Cute."),
                ("recruiter", "If I cannot pitch it in a mall, do not pitch it in a hearing."),
            ),
        ),
        (
            "Refugee Waves",
            "This view is logistics first: housing, schools, and a legal status that is not a 10-year maybe.",
            (
                "A moral welcome without beds is a press conference that becomes a shelter floor.",
                "Status that cannot work legally is how you grow a gray market and a backlash.",
                "Cities that take the arrival without the reimbursement are not saints. They are invoices.",
            ),
            (
                ("gym-cots", "The welcome was a gym. The gym was a school. That is the policy arriving."),
                ("work-card", "Let them work or stop pretending this is temporary. Limbo is a labor policy."),
                ("invoice", "We housed them. Send the check. Compassion is a budget line or it is a speech."),
            ),
        ),
        (
            "War Fatigue",
            "A larger, quieter group is done with open tabs: endless clips, unclear metrics, and a foreign policy that never clocks out.",
            (
                "Attention is a resource. A war that cannot describe progress will lose the living room, then the vote.",
                "Fatigue is not isolationism. It is a demand for a theory of enough.",
                "People can hold two truths: a just cause, and a refusal to live inside the clip forever.",
            ),
            (
                ("open-tab", "I still think they should win. I also want a metric that is not a montage."),
                ("enough", "Define enough. If you cannot, you are asking for a blank decade."),
                ("two-truths", "I am not a crank. I am tired. Those are allowed to coexist."),
            ),
        ),
    ),
    "Tax Fights": faces(
        (
            "Rate Brackets",
            "The loud argument is still the top rate versus the next deduction — a morality play that ignores what actually gets filed.",
            (
                "A headline rate that nobody with a good accountant pays is a brand, not a base.",
                "Brackets that do not move with housing costs are a stealth increase on work in expensive metros.",
                "If the fight is only the top number, the rest of the return gets looted in peace.",
            ),
            (
                ("headline", "They argued 37 versus 39. My effective is 19 with a better firm. Cute play."),
                ("cola-housing", "The bracket did not notice the rent. That is a raise for the Treasury, not for me."),
                ("top-number", "Keep the camera on the rate. The footnote is where the money lives."),
            ),
        ),
        (
            "Loopholes",
            "This cluster wants the code read as a map of who has a lobbyist: pass-through games, carried interest, and credits that never sunset.",
            (
                "A preference that survives every 'reform' is not a glitch. It is the point of the coalition.",
                "Credits stacked until a profitable firm pays a thank-you note are why people think the system is fake.",
                "Sunset clauses that never sunset are how a temporary idea becomes a family office.",
            ),
            (
                ("passthrough", "Wages are wages until they are a partnership. Then they are a costume."),
                ("carry", "I get it. Risk. I also get a W-2. Harmonize those without a seminar."),
                ("never-sunset", "The credit was for 2009. It is a personality now."),
            ),
        ),
        (
            "Local Levies",
            "Property-tax revolts treat the school millage as the only tax people can see — and the only one they can punch.",
            (
                "When the visible tax is the house, every city service becomes a war on people who stayed.",
                "Caps that starve the school and inflate the sale price are a gift to the already-housed.",
                "If you want less property tax, you need another base. Rage at the envelope is not a base.",
            ),
            (
                ("envelope", "The only bill with my name on it is the millage. Of course I hate it. That is the design."),
                ("cap-stay", "We capped the tax and uncapped the house price. I can leave. My kid's teacher cannot."),
                ("other-base", "Find income or sales and then we can talk. Until then the house is the piñata."),
            ),
        ),
        (
            "Wealth Taxes",
            "A smaller group wants a mark-to-market or a net-worth levy; opponents call valuation a hall of mirrors.",
            (
                "Unrealized gains that fund a lifestyle are income in every sense except the one the code chose.",
                "Valuation of private assets is a fight. So is a world where wage earners prepay and founders never sell.",
                "If the administrative mess is the knockout, propose the cleaner cousin: better estate and realization rules. Do not pretend the mess is the morality.",
            ),
            (
                ("unrealized", "He borrowed against the stock and lived. I got a W-2. One of us paid pay-as-you-go."),
                ("409a-hall", "You try marking a biotech at midnight. That is the objection. It is not nothing."),
                ("estate-cousin", "I will take a working estate tax before I take a vibe about billionaires. Ship the cousin."),
            ),
        ),
    ),
    "Statehouses": faces(
        (
            "Preemption",
            "Cities describe a capitol that vetoes plastic bags, wages, and zoning — home rule as a nostalgia brand.",
            (
                "A legislature that forbids a minimum wage and a bus lane is running the city from a building that does not take the bus.",
                "Preemption is how statewide donors cancel a local majority.",
                "If the city cannot try a policy, the laboratory of democracy is a speech.",
            ),
            (
                ("bag-ban", "We voted for a wage. They voted it off the table. That is not federalism. That is a parent."),
                ("donor-map", "The lobbyist does not live in the precinct. The preemption is their local government."),
                ("lab-dead", "You cannot copy what you are forbidden to run. Thanks for the laboratory."),
            ),
        ),
        (
            "School Bills",
            "Parents, teachers, and boards live inside a stack of bills about books, bathrooms, and what a counselor may say.",
            (
                "A statewide script for a local classroom is how you get teachers who teach the statute, not the student.",
                "Parents deserve a syllabus. They do not deserve a snitch line.",
                "The pile of bills is the point: exhaustion is a legislative strategy.",
            ),
            (
                ("script", "I have a binder of what I may not say. I do not have a binder of paper. Priorities."),
                ("tip-line", "A hotline for lesson plans is not involvement. It is a neighborhood watch for verbs."),
                ("stack", "They dropped seven bills in a week. The strategy is oxygen."),
            ),
        ),
        (
            "Maps",
            "This cluster treats redistricting as the election before the election — machines that choose voters.",
            (
                "A map that survives a 15-point swing is not representation. It is insulation.",
                "Commissions help. They also get captured. Sunlight on the shapefile is the minimum.",
                "If your party needs a 7-3 map to feel safe, you do not have a majority. You have a cartographer.",
            ),
            (
                ("15-point", "The incumbent survived a wave. The voters did not survive the map."),
                ("shapefile", "Publish the file. If you are proud of it, you can stand next to the squiggle."),
                ("7-3", "We are a 50-50 state with a 7-3 delegation. That is not a vibe. That is a drawing."),
            ),
        ),
        (
            "Attorneys General",
            "AGs as national politicians: multistate suits, letterhead wars, and a state brief that is actually a presidential primary.",
            (
                "When 20 AGs file the same brief, you are looking at a party, not a locality.",
                "Consumer protection is the job. National cable-news briefs are the hobby. Watch which one gets the staff.",
                "Forum shopping for a friendly district plus an AG is how law gets made without a legislature.",
            ),
            (
                ("20-names", "The brief has more AGs than facts. It is a choir."),
                ("hobby", "We have payday lenders at home. The office is suing a platform for a clip."),
                ("forum", "Pick a judge, pick a statute, pick a press hit. That is the new federalism."),
            ),
        ),
    ),
    "Protest Rights": faces(
        (
            "Permits",
            "Organizers treat the permit as both a safety plan and a veto dressed as traffic control.",
            (
                "A fee that only a 501(c)(3) can pay is a speech tax.",
                "Spontaneous protest is a constitutional category. A 30-day application is how you erase it.",
                "If the city can move you to a cage next to the freeway, it can hide you. Call that what it is.",
            ),
            (
                ("speech-tax", "The insurance rider cost more than the sound system. That is the permit."),
                ("30-day", "The news happened on Tuesday. The form wants last month. That is a veto."),
                ("freeway-cage", "They offered us a parking lot by the on-ramp. We declined to be a diorama."),
            ),
        ),
        (
            "Campus Rules",
            "Universities try to be parks, landlords, and brands at once — time-place-manner as a maze that appears when the cameras do.",
            (
                "A public quad with a private-security soul will lose in court or in the yearbook. Pick a theory.",
                "Rules that are unenforced until the cause is unpopular are not rules. They are a preference.",
                "Encampments force a content-neutral test that administrators fail in real time.",
            ),
            (
                ("quad-theory", "Either this is a public forum or it is a lawn. The pepper spray suggested a lawn."),
                ("until-cameras", "The table policy was a rumor until this week. Then it was a statute."),
                ("content-neutral", "They discovered time-place-manner when the signs got specific. I took notes."),
            ),
        ),
        (
            "Kettling",
            "A harder cluster talks about crowd-control tactics that turn a march into a trap — and a mass-arrest statistic.",
            (
                "A police line that closes the exit is not crowd control. It is a capture plan.",
                "Less-lethal is still kinetic. Eye injuries are not a metaphor.",
                "Mass process-for-later is how you chill the next march without a conviction.",
            ),
            (
                ("no-exit", "They let us in. They did not let us out. That is the tactic. Name it."),
                ("less-lethal", "The munition was less lethal and my friend is still seeing a specialist. Accurate, I guess."),
                ("cite-later", "A thousand citations, a dozen charges, a quieter street next time. That is the point."),
            ),
        ),
        (
            "Night Marches",
            "Residents and marchers argue about after-dark actions: visibility versus sleep, media versus broken glass.",
            (
                "A 2am march is a different speech act than a noon rally. The law can notice time without banning the claim.",
                "Journalists who only show up for the fire miss the 4pm permit speech. That skew is now the politics.",
                "People who live on the route have standing. So do the people the route is about. Pretending one is fake is how it stays hot.",
            ),
            (
                ("2am", "I support the cause. I also have a shift at 6. Both of those are real."),
                ("camera-fire", "The noon march did not make the feed. The dumpster did. That is an editor, not a movement."),
                ("route", "My block is the set. Talk to us like we are the public, not the scenery."),
            ),
        ),
    ),
    "Executive Power": faces(
        (
            "Emergency Orders",
            "This cluster is still in the pandemic hangover: how long a governor or president may govern by PDF.",
            (
                "An emergency that outlives the emergency is a standing legislative workaround.",
                "Speed is the case for orders. Sunsets are the case for a republic. You can have both if you write them.",
                "Courts that only notice this when the other party holds the pen are teaching a lesson about pens.",
            ),
            (
                ("sunset", "I will live with a 30-day order. I will not live with a 30-month one. Put a clock on it."),
                ("pdf-gov", "The legislature was a spectator. The PDF was the session."),
                ("other-pen", "They discovered the constitution when the signature changed. I kept the clip."),
            ),
        ),
        (
            "Agencies",
            "Lawyers argue over how much a statute may hand to a specialist — expertise versus a veto from a later court.",
            (
                "If Congress writes 'reasonable', someone has to fill the blank. Pretending judges are better chemists is a mood.",
                "A major-questions doctrine that is a vibe will produce a government of stay orders.",
                "Understaffed agencies with huge statutes are how you get both overreach and paralysis.",
            ),
            (
                ("reasonable", "They wrote a word and left. Someone has to be the adult. Today it is a 28-year-old and a comment docket."),
                ("vibe-major", "Is this major? Ask a clerk. That is not a doctrine. That is a shrug."),
                ("comment-docket", "Expertise is real. So is capture. Sunlight on the docket is the boring fix."),
            ),
        ),
        (
            "Appointments",
            "Vacancies, acting titles, and a Senate that treats every name as a hostage — personnel as policy by attrition.",
            (
                "An acting official in year three is not a placeholder. They are the administration.",
                "Holds that have nothing to do with the nominee are how a senator becomes a ministry of everything.",
                "If the job cannot be filled, the statute is a fantasy. Write a government you will staff.",
            ),
            (
                ("acting-3", "We are on our fourth acting. The org chart is a rumor."),
                ("hold", "The hold is about a different bill. The nominee is a prop. The bureau is empty."),
                ("staff-it", "You authorized a watchdog and then refused the watcher. That is a punchline."),
            ),
        ),
        (
            "Norms",
            "A weary view treats unwritten rules as the actual constitution — and notices they only bind the people who still believe in them.",
            (
                "A norm is a gentleman's agreement. It fails the day one side hires fewer gentlemen.",
                "Write it down or lose it. Nostalgia is not a check.",
                "People asking for norms after breaking them are not serious. People refusing to write the replacement are not either.",
            ),
            (
                ("gentlemen", "We had a custom. Then we had a clip. The custom lost."),
                ("write-it", "If it matters, it is a rule. If it is a vibe, it is already gone."),
                ("both-sides-norm", "I will take a statute over a lecture from the last person who treated the lecture as optional."),
            ),
        ),
    ),
}
