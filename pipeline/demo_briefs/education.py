"""Education extras beyond Education Reform."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "College Value": faces(
        (
            "ROI",
            "Borrowers and parents treat the degree as a bet that has to beat rent, interest, and lost wages — not a ritual.",
            (
                "If the median graduate cannot clear the loan and a one-bedroom, the brochure's 'investment' line is a slogan.",
                "Opportunity cost is the tuition nobody prints: four years out of a trade wage while the sticker price compounds.",
                "A ranking that ignores debt-to-earnings is a prestige contest, not consumer protection.",
            ),
            (
                ("spread-sheet", "I ran the numbers on my cousin's B.A. The degree loses to the electrician until year 14, and that is before interest."),
                ("first-gen-ledger", "We did everything right and still need a roommate. ROI was the slide. Rent is the outcome."),
                ("counselor-truth", "I stopped telling kids 'college is always worth it'. I show them the cohort default rate instead."),
            ),
        ),
        (
            "Humanities",
            "Defenders say the point of college is judgment, language, and citizenship — and that those still have a labor market, just a quieter one.",
            (
                "A republic that cannot read a statute or a poem will still hire people. It will hire worse ones.",
                "The collapse is not that philosophy majors exist. It is that we defunded the public jobs that used to hire them.",
                "Writing, ethics, and history are job skills that show up later, which is why dashboards cannot see them.",
            ),
            (
                ("adjunct-lit", "I teach close reading to nurses and engineers at 8am. Their jobs need it. The legislature does not."),
                ("museum-fellow", "The humanities pipeline is not dead. It is unpaid. Prestige ate the entry wage."),
                ("dean-memo", "They want 'critical thinking' in the mission and fewer English lines in the budget. Pick one."),
            ),
        ),
        (
            "Trade Paths",
            "This cluster wants apprenticeships, nursing, and shop treated as first-class routes with the same counseling energy as the flagship campus.",
            (
                "Guidance offices still call a union card a backup plan while the HVAC waitlist is six months long.",
                "A two-year credential that leads to a license is a clearer contract than a vague bachelor's in 'studies'.",
                "The stigma is the policy: we built a status ladder and then acted shocked that the trades went hungry.",
            ),
            (
                ("local-ibe", "I make more than my cousin with the thesis. The counselor still whispered 'you could do better'."),
                ("shop-closed", "They sold the lathes, then begged manufacturers to come back. The lab was the recruitment."),
                ("rn-bridge", "The fastest respectable ladder in this town is still nursing. Fund the seats like a stadium."),
            ),
        ),
        (
            "Rankings",
            "Skeptics treat US News-style lists as a prestige arms race that raises tuition and punishes schools that serve the students who need them.",
            (
                "Selectivity is a luxury good. Reward it and you punish the campus that admits the kid who actually needs the education.",
                "Alumni giving and SAT medians are not teaching quality. They are a country club with a methodology footnote.",
                "Chasing a rank is how you get climbing walls, merit aid for the already-admitted, and a quiet freeze on need.",
            ),
            (
                ("yield-games", "We spent more on a rankings consultant than on the writing center. The brochure looks great."),
                ("merit-hoard", "They call it merit aid. It is a discount to buy SAT medians so the list does not slip."),
                ("land-grant", "Our job is the county. The list's job is the zip codes that already have tutors."),
            ),
        ),
    ),
    "AI in Class": faces(
        (
            "Cheating",
            "Teachers describe take-home essays as a broken assessment once a chatbot can draft a B- in twelve seconds.",
            (
                "If the assignment can be completed without a mind in the room, it was already a weak assignment — the model just made that obvious.",
                "Honor codes cannot police a tool that lives in every pocket. Design has to change, not just the syllabus warning.",
                "Catching AI is an arms race that turns teachers into detectors instead of readers.",
            ),
            (
                ("comp-101", "I got 40 near-identical intros about 'the importance of storytelling'. Nobody talks like that. The model does."),
                ("honor-board", "We cannot hold a tribunal for every comma that looks generated. The assessment has to move in-class."),
                ("night-grader", "I miss the bad essays. At least they were theirs."),
            ),
        ),
        (
            "Tutors",
            "The optimistic cluster treats models as a 24-hour tutor for kids who never had one — if the school designs for it instead of pretending it is not there.",
            (
                "A patient explainer at 11pm is a public good for the kid whose parent works second shift.",
                "The danger is not help. It is help with no teacher in the loop to catch the fluent wrong answer.",
                "Used as Socratic questions, it is a ladder. Used as a paragraph vending machine, it is a crutch.",
            ),
            (
                ("night-shift-dad", "The bot sat with my kid on fractions while I was on the floor. That is not cheating. That is the village we do not have."),
                ("math-coach", "I make them show the prompt. If the prompt is 'explain like I'm stuck on step 3', I am fine. If it is 'write the proof', I am not."),
                ("ell-room", "Translation plus worked examples is the first tutor some of my students have ever had. Ban it and you ban them."),
            ),
        ),
        (
            "Policy",
            "Administrators want a district rule that is more than a banned-list PDF: when it is allowed, how it is cited, and who is liable when it is wrong.",
            (
                "Silence is a policy. It just outsources the ethics to whichever teacher is least exhausted.",
                "A tool the vendor sold to the board cannot be 'unauthorized' in the classroom the next week without a fight.",
                "Assessment, privacy, and disability accommodations have to be in the same memo or the memo is theater.",
            ),
            (
                ("board-packet", "We passed 'use AI ethically' and no one can define it. That is a poster, not a policy."),
                ("union-note", "Do not make me the copyright cop for a product the superintendent demoed at convocation."),
                ("spec-ed", "If the accommodation is a scribe, a model might be the scribe. Write that down before a parent has to sue."),
            ),
        ),
        (
            "Equity",
            "This view says the real split is who gets a paid copilot, a quiet room, and a teacher who knows how to use it — not whether AI exists.",
            (
                "Premium models and home broadband are the new graphing calculator: optional on paper, required in practice.",
                "A ban that only works in the rooms with no phones will punish the kids who already had the least help.",
                "District licenses can level the floor. Personal ChatGPT Plus in the suburbs will still raise the ceiling.",
            ),
            (
                ("title-i", "Half my class shares a phone. The other half has Super Grok or whatever it is called this month. That is tracking."),
                ("librarian", "We put the district model on library machines. Usage spiked among kids who never had a tutor."),
                ("pta-thread", "Parents in the group chat are buying 'AI coaches'. The school is still arguing about the honor code."),
            ),
        ),
    ),
    "School Safety": faces(
        (
            "Drills",
            "Parents and teachers argue that lockdown drills have become the default safety policy even when they scare kids more than they prevent harm.",
            (
                "A drill that looks like the real event trains children to expect violence without teaching them how to stay safe.",
                "Time spent on ALICE days is time not spent on counselors, locked vestibules, or threat assessment.",
                "Kids who already live with that fear should not have to rehearse it on a school-day calendar.",
            ),
            (
                ("lockdown-mom", "We had three lockdown drills this month. My third-grader now asks if today is the day someone comes."),
                ("alicesub", "If the plan is practice dying, we do not have a safety plan. We have a ritual with a substitute teacher."),
                ("grade3-desk", "Counselors are part-time. The ALICE trainer is a full-day sub. That budget is a worldview."),
            ),
        ),
        (
            "Counselors",
            "This cluster says the real safety intervention is mental-health staffing, not another hardware grant.",
            (
                "Most campus crises start as a student in distress that a 700-to-1 counselor ratio cannot possibly catch.",
                "A metal detector does not sit with a kid who posted a goodbye. A person does.",
                "Until every campus has a full-time counselor and a threat-assessment team, drills are theater around an empty office.",
            ),
            (
                ("caseload700", "I have 700 students and a closet. You cannot threat-assess a spreadsheet."),
                ("psych-wait", "The district bought a camera system the same week they froze the counselor hire. Priorities are a purchase order."),
                ("parent-iep", "My kid asked for help in October. The intake is March. Safety is a waitlist with a lock on the classroom door."),
            ),
        ),
        (
            "Design",
            "Facilities people treat school safety as a building problem: sightlines, vestibules, and rooms that actually lock.",
            (
                "A classroom that cannot lock from the inside is a policy failure hiding in a floor plan.",
                "Single-point entries and interior windows beat a motivational poster about 'see something'.",
                "Portables, open campuses, and 1970s courtyards set more risk than any curriculum fight.",
            ),
            (
                ("facilities-am", "We still have classrooms that do not lock from the inside. That is not a training gap."),
                ("vestibule", "The bond paid for a scoreboard. The main office still opens onto a hallway with no second door."),
                ("portable-row", "Half the school is in portables with a padlock aesthetic. Hardening a trailer is a punchline."),
            ),
        ),
        (
            "Police",
            "A smaller cluster wants armed officers and faster tactical response treated as the actual last line, not a culture-war prop.",
            (
                "A counselor cannot stop an active attacker who is already in the building; someone with a radio and a weapon might.",
                "Response time is the variable parents actually live with after the cameras fail.",
                "SRO programs are uneven, but removing them without a replacement is not a safety plan either.",
            ),
            (
                ("sro-desk", "I am not a hallway cop cartoon. I am the person who knows which kid has been spiraling since October."),
                ("wait-time", "The sheriff is 18 minutes out. That sentence is the whole argument for having someone on campus."),
                ("after-action", "We can argue about police in schools after the door locks and the counselor exists. Until then it is not either-or."),
            ),
        ),
    ),
    "Literacy": faces(
        (
            "Phonics",
            "The science-of-reading camp says guessing from pictures was a generation-scale error, and systematic phonics is the repair.",
            (
                "A child who cannot decode cannot comprehend, no matter how rich the classroom discussion sounds.",
                "Cueing from context is a habit that hides non-readers until fourth grade, when the pictures go away.",
                "This is not nostalgia for drill. It is matching instruction to how written English actually works.",
            ),
            (
                ("k-room", "I stopped asking 'what would make sense?' and started asking 'what does that spell?'. The quiet kids caught up."),
                ("parent-decode", "My second-grader was a 'great guesser'. That is a polite word for cannot read."),
                ("curric-dir", "We spent years on three-cueing workshops. The NAEP did not care about our workshop hours."),
            ),
        ),
        (
            "Screens",
            "This view treats phones and short video as the rival literacy program, training skimming until a chapter feels like a punishment.",
            (
                "Attention is the prerequisite. A device that pays for interruption will beat a novel without a school-level fight.",
                "Reading stamina is a muscle. TikTok is not a warm-up.",
                "Banning phones in the classroom is the first literacy intervention that does not require a new curriculum adoption.",
            ),
            (
                ("phone-bin", "The period after we locked the pouches, I heard pages turn. That is data."),
                ("ya-librarian", "They can read. They will not sit. The rival text is 15 seconds and it laughs."),
                ("night-scroll", "Homework vs. the infinite feed is not a fair fight. Pretending it is 'parenting' lets the product off."),
            ),
        ),
        (
            "Libraries",
            "Librarians argue that a staffed collection is literacy infrastructure, and that emptying it for a maker space or a ban list is the real crisis.",
            (
                "A kid without a trusted adult recommending the next book does not magically become a reader from a phonics app.",
                "Access is the intervention: hours, buses, and a room that is not also a testing center.",
                "Removing books is easier than staffing clerks. That is why it keeps winning board meetings.",
            ),
            (
                ("shelf-check", "We are on year two without a full-time librarian. The room is a storage closet with posters."),
                ("hold-list", "The hold list for graphic novels is the actual reading program. Fund the copies."),
                ("ban-night", "They came for 12 titles and left with the clerk's hours. Censorship is cheaper than staffing."),
            ),
        ),
        (
            "Tutors",
            "High-dosage tutoring is the cluster's practical answer: a human, three times a week, on the skill the kid actually missed.",
            (
                "A 25-to-1 classroom cannot do the catch-up a 1-to-3 table can, especially after pandemic unfinished learning.",
                "Tutoring that is optional after the bus leaves will be used by the kids who need it least.",
                "If the district can find money for a new stadium board, it can find money for people who sit with struggling readers.",
            ),
            (
                ("dose-3x", "Three 30-minute sessions a week with the same adult. That is the only thing that moved my D's."),
                ("bus-gap", "After-school tutoring is a transportation policy. The kids who need it miss the late bus."),
                ("retired-teach", "I came back to tutor. I am not a savior. I am the ratio the classroom never had."),
            ),
        ),
    ),
    "Admissions": faces(
        (
            "Testing",
            "One cluster wants SAT and ACT back as the least-bad equalizer once essays and activities became a coaching market.",
            (
                "A Saturday morning test is imperfect. A polished 'spike' built by consultants is a wealth test with better lighting.",
                "Test-optional became test-optional-unless-you-need-aid, which is a quieter sorting hat.",
                "Grade inflation made transcripts glow. A common exam at least names the same skill.",
            ),
            (
                ("sat-sat", "My public-school kid cannot buy a nonprofit on the resume. She can sit for a test. Bring it back."),
                ("optional-trap", "Optional means submit if you are high. Hide if you are not. That is still a test, just meaner."),
                ("hs-counsel", "A's mean nothing when 40% of the class has them. The SAT was the only shared ruler we had."),
            ),
        ),
        (
            "Legacy",
            "Critics treat alumni preference as inherited admissions — a loyalty program that crowds out the kid who actually needs the seat.",
            (
                "A thumb on the scale for donors' children is not tradition. It is a waitlist with a last name.",
                "You cannot brag about mobility and keep a family discount on the most scarce good the college sells.",
                "Ending legacy is the rare fairness reform that does not require a new exam, only a spine.",
            ),
            (
                ("waitlist-kid", "I was deferred so someone's roommate's kid could keep a family tradition. Say that in the viewbook."),
                ("dev-office", "They told faculty merit is sacred and then asked me to flag the last names. I have the spreadsheet."),
                ("first-gen", "My parents did not go here. That is not a character flaw. Stop scoring it like one."),
            ),
        ),
        (
            "Essays",
            "This view says the personal statement is a ghostwritten luxury good that rewards trauma plots and paid editors.",
            (
                "A 650-word essay is now a cottage industry. The voice on the page is often a counselor's.",
                "Admissions that hunt for 'authentic struggle' create an incentive to perform pain.",
                "If writing matters, score a supervised sample. If it does not, stop pretending the Common App box is literature.",
            ),
            (
                ("essay-mill", "We paid $800 to make her sound like herself. That sentence should end the genre."),
                ("trauma-plot", "Kids ask me if their life is 'enough' for the essay. We turned childhood into a pitch."),
                ("eng-teacher", "Give them 50 minutes in a gym with a prompt. I will believe that paragraph."),
            ),
        ),
        (
            "Yield",
            "Enrollment managers describe the real sport as predicting who will say yes — merch, early decision, and discounts as inventory control.",
            (
                "Early decision is a binding contract sold as romance. It is a yield tool that lands hardest on kids who cannot risk the price.",
                "Merit discounts to buy a class that 'looks right' are price discrimination with a viewbook smile.",
                "The waitlist is a hedge, not a judgment. Treating it like a moral ranking is how families go insane in April.",
            ),
            (
                ("ed-bind", "Sign here so we can lock tuition before you see the other packages. They call it demonstrated interest."),
                ("waitlist-bot", "I am not a person in April. I am a yield model. The portal even feels like an airline."),
                ("finaid", "We discount the full-pay kid to steal them from a peer. Need is the residual."),
            ),
        ),
    ),
    "Community College": faces(
        (
            "Transfer",
            "Students describe the transfer maze — lost credits, changing articulation, a flagship that treats the two-year campus as a feeder with amnesia.",
            (
                "A credit that dies at the county line is a tax on the student who did the cheaper, smarter thing first.",
                "Guaranteed admission that still requires a scavenger hunt of 'hidden prereqs' is not a pathway.",
                "The flagship's general-education fortress is how mobility becomes a brochure word.",
            ),
            (
                ("lost-credits", "I repeated Comp II because a human did not check a box. That was a semester of rent."),
                ("map-404", "The transfer map on the website is from 2019. My advisor printed it like scripture."),
                ("junior-year", "They sold 'start here, finish there'. I started here and finished in a parking lot of petitions."),
            ),
        ),
        (
            "Workforce",
            "This cluster wants community colleges judged as the region's training floor: CDL, HVAC, allied health, and employers at the table.",
            (
                "A welding night class that ends in a job is a better public return than a vague associate's with no license.",
                "Employers who complain about talent but will not fund slots or release workers for class are the other half of the shortage.",
                "Short credentials have to stack, or you have built a treadmill of certificates that expire.",
            ),
            (
                ("night-hvac", "I left with a license and a van. That is a college. Call it whatever you want."),
                ("plant-hr", "We need 40 techs. We donated a banner. Donate an instructor and a cohort instead."),
                ("stackable", "My certificate died when the vendor changed the exam. Stack it onto a credit or stop selling it."),
            ),
        ),
        (
            "Funding",
            "Advocates say the community college is asked to be the mobility engine on the leftover appropriation after the flagship takes the headline.",
            (
                "Outcomes funding that punishes open-access schools for serving the students who need more time is a perverse scoreboard.",
                "Free community college without a faculty line is a press conference that shows up as 40-person English sections.",
                "The cheapest college is not cheap if the student cannot get a seat in the gatekeeper math.",
            ),
            (
                ("section-closed", "College algebra closed in two days. Dual enrollment ate the seats. The adults who pay taxes got a waitlist."),
                ("outcomes-tax", "They pay us for completions and then send us every student the university does not want. Cute."),
                ("adjunct-share", "Seventy percent adjuncts is not a staffing model. It is a confession about the appropriation."),
            ),
        ),
        (
            "Childcare",
            "Parent-students treat on-campus care as the actual enrollment policy — without a slot, the class is theoretical.",
            (
                "A night section with no infant room is a class offered only to people who already have a village.",
                "Pell and a syllabus cannot watch a toddler. The waitlist at the campus center is the drop rate.",
                "Workforce programs aimed at women that ignore childcare are a labor-market cosplay.",
            ),
            (
                ("infant-list", "I got into nursing. I did not get into the campus daycare. Guess which one ended the plan."),
                ("night-class", "They schedule allied health at 6pm like parents do not exist. Hire a sitter in the building or stop recruiting us."),
                ("advisor", "The number one 'stop out' reason I hear is childcare. We still count it as motivation."),
            ),
        ),
    ),
    "Faculty Labor": faces(
        (
            "Adjuncts",
            "Contingent faculty describe the modern campus as a business that runs on people with no office, no benefits, and three institutions on the odometer.",
            (
                "A course that costs students thousands cannot be staffed by a scholar paid like a gig driver with a syllabus.",
                "No office hour is not a personality. It is a building that will not give you a key.",
                "The quality crisis is a payroll strategy: hire the PhD, decline the appointment.",
            ),
            (
                ("freeway-flyer", "Three campuses, 90 miles, no health plan. I am the general education curriculum."),
                ("no-key", "Students wanted office hours. Security wanted a contractor badge. I met them in a stairwell."),
                ("term-to-term", "I find out if I exist in August. The catalog found out in March."),
            ),
        ),
        (
            "Tenure",
            "This cluster treats tenure as academic freedom's last furniture, and the post-tenure freeze as how universities buy silence cheap.",
            (
                "Without a job that can survive an angry trustee, research on local power becomes a hobby for the independently wealthy.",
                "A campus of revolving contracts will not tell the president the program is a turkey.",
                "Tenure is not a hammock. It is the reason a scientist can say the donor is wrong.",
            ),
            (
                ("ntt-majority", "We are 30% tenure-line and 100% 'family'. Only one of those gets to vote on the curriculum."),
                ("donor-chill", "I changed a case study after a call from advancement. That is the opposite of a university."),
                ("senate-floor", "They want innovation from people who can be non-renewed by a dean's mood. Good luck."),
            ),
        ),
        (
            "Strikes",
            "Organizing drives frame picket lines as the only remaining lever once shared governance became a listening session.",
            (
                "A work stoppage is what you get when the budget can find a stadium and cannot find a cost-of-living clause.",
                "Students are not scabs. They are the constituency being asked to cross a picket they did not create.",
                "Public sympathy shows up when graders vanish. That is ugly, and it is also how higher ed finally looks at payroll.",
            ),
            (
                ("picket-am", "We are not against the students. We are against a board that pays us like the students' rent is optional."),
                ("ta-unit", "If the university can find money for a coach, it can find money for the people grading the midterms."),
                ("admin-email", "The 'we are a family' email hit during the strike. Families do not hire replacement graders."),
            ),
        ),
        (
            "Research",
            "Lab leads and scholars say the job has become grant hunting, overhead, and metrics — with teaching and mentoring as unfunded mandates.",
            (
                "Indirect costs and proposal mills crowd out the actual experiment. The university is a development office with a lab attached.",
                "Counting papers like piecework is how you get five slice-and-dice articles and one idea.",
                "Graduate labor is the hidden subsidy. Pretending it is 'training' does not pay the rent.",
            ),
            (
                ("nih-roulette", "I spent eight months on a grant that lost on a 2. That is not science. That is a lottery with a biosketch."),
                ("overhead", "The university loves my indirects and hates my mice. Guess which one gets a building."),
                ("grad-rent", "My students do the work. Their stipend is a housing joke. Call it training if you need to sleep."),
            ),
        ),
    ),
    "EdTech Fatigue": faces(
        (
            "Licenses",
            "Teachers describe a stack of platforms that do not talk to each other, each with a renewal that outlives the pedagogy.",
            (
                "A district that buys seven dashboards has not bought instruction. It has bought logins.",
                "The license outlasts the champion who understood it, and then the next teacher inherits a graveyard tab.",
                "If the tool needs three PD days to become usable, it is not a classroom tool. It is a vendor event.",
            ),
            (
                ("tab-graveyard", "I have 11 educational logins and one brain. The kids can smell which tab is busywork."),
                ("renewal", "We paid for a literacy suite nobody opens. Canceling it would require a person who remembers the contract."),
                ("interop", "Grades live in four systems. None of them is the gradebook I am evaluated on."),
            ),
        ),
        (
            "Surveillance",
            "This cluster treats classroom software as a telemetry layer on children — keystroke flags, webcam proctoring, and data that outlives the semester.",
            (
                "A gooseneck webcam that watches a 15-year-old take a quiz is not integrity. It is a suspicion architecture.",
                "Flagging 'self-harm language' with no counselor attached is a liability product, not care.",
                "Homework should not be a telemetry event the vendor can resell as 'insights'.",
            ),
            (
                ("proctor-eye", "My kid cried through geometry because a stranger watched her room for cheating. That is not math."),
                ("flag-queue", "The software flagged a poem. The counselor is at another campus on Tuesdays. Cute pipeline."),
                ("admin-off", "Turn the keystroke watcher off. If you cannot trust a quiz, write a better quiz."),
            ),
        ),
        (
            "PD",
            "Educators want professional development that is practice in a room, not a slide deck from the people who sold the license.",
            (
                "Clicking through a 40-minute module is not training. It is compliance with a certificate at the end.",
                "Teachers will use a tool they saw work with their kids. They will not use a keynote.",
                "PD time is the scarcest instructional resource. Spending it on a vendor logo is a staffing choice.",
            ),
            (
                ("module-hell", "I 'completed' three PD courses on a Sunday. I could not demo a single one on Monday."),
                ("coach-please", "Give me a coach in my room for a period. Keep the inspirational breakfast."),
                ("early-release", "Early release for a login demo is how you teach us that our time is the free tier."),
            ),
        ),
        (
            "Outages",
            "When the gradebook, attendance, and curriculum live in the cloud, a vendor outage becomes a snow day without the snow.",
            (
                "A school that cannot take attendance without a status page is not modern. It is fragile.",
                "Paper fallback is not nostalgia. It is the continuity plan the contract forgot.",
                "Mission-critical instruction should not sit behind a single company's Tuesday incident.",
            ),
            (
                ("status-red", "SIS down, 900 kids in the gym, no roster. The cloud is a weather system now."),
                ("paper-bin", "I keep a paper seating chart like a prepper. Last outage I was the only adult who knew who was missing."),
                ("curric-lock", "The lesson lives in the platform. The platform 503'd. We watched a video. That is not a curriculum."),
            ),
        ),
    ),
    "Civics Teaching": faces(
        (
            "Curriculum",
            "Teachers want a civics sequence that includes how a city actually works — budgets, courts, and agencies — not just the Preamble poster.",
            (
                "A graduate who can name the branches and cannot read a local agenda has not been taught citizenship.",
                "Contested history belongs in the open. A list of banned inquiries is not a standard.",
                "Practice — mock hearings, budgeting games, covering a board meeting — beats a multiple-choice founding myth.",
            ),
            (
                ("agenda-pdf", "I take seniors to a zoning hearing. Half of them did not know the city had one. That is the gap."),
                ("std-fight", "They want 'founding principles' and no Reconstruction. That is not civics. That is a brand."),
                ("mock-trial", "The day they argued a fourth-amendment stop, they learned more than from the chapter quiz."),
            ),
        ),
        (
            "Polarization",
            "This view says the classroom is being asked to host the country's fight, and that the job is teaching disagreement without turning the room into cable news.",
            (
                "Kids arrive with their parents' feed. Pretending the room is neutral just hands the hour to the loudest clip.",
                "Ground rules and primary sources are the anti-viral technology. Hot takes are not a pedagogy.",
                "A teacher who is scared to run a structured controversy will default to worksheets, and worksheets are how civics dies.",
            ),
            (
                ("clip-kid", "He quoted a streamer as if it were a statute. Our job is to slow that down, not to dunk."),
                ("parent-email", "I got three emails before the unit started. I still ran the seminar. Fear is the intended product."),
                ("circle", "We do disagreement with a timer and a text. It is boring. It is the opposite of the algorithm."),
            ),
        ),
        (
            "Local Gov",
            "A practical cluster wants civics to start at city hall: who plows, who zones, who runs the school board, and how you get on the agenda.",
            (
                "National politics is a spectator sport. Local government is the one that can still answer an email.",
                "If students never see a public comment, they will think democracy is a presidential horse race.",
                "A field trip to public works teaches more about the social contract than a week on the Electoral College.",
            ),
            (
                ("public-works", "The water plant tour did more for 'what taxes do' than my beautiful slide on locke."),
                ("board-night", "Two students commented on the late-bus item. That is a civics credit. The AP exam is a trivia night."),
                ("mayor-hours", "Nobody in the class could name the mayor. Everybody could name a senator. That is a curriculum bug."),
            ),
        ),
        (
            "Media",
            "This face treats news literacy as civics: feeds, receipts, and the difference between a primary document and a rage clip.",
            (
                "Citizenship now includes not getting conscripted by a ranking system that wants another tap.",
                "Lateral reading — leave the page, check the claim — is the civic skill the pamphlet never mentioned.",
                "A course that ignores platforms is teaching a 1998 public square.",
            ),
            (
                ("lateral", "I make them open a second tab before they believe me. That is the whole unit."),
                ("receipts", "We annotate a viral post the way we used to annotate a cartoon. Same lies, faster."),
                ("feed-civics", "If you cannot explain a For You page, you cannot explain modern persuasion. Sorry, Madison."),
            ),
        ),
    ),
}
