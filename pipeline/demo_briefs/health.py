"""Health extras beyond Public Health."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Hospital Staffing": faces(
        (
            "Travel Nurses",
            "Floor staff treat travel rates as a tell: the hospital will pay a premium to a stranger before it will retain the people who know the unit.",
            (
                "A travel contract at twice the staff rate is not a shortage. It is a preference.",
                "Units that run on travelers lose the memory that keeps patients alive at 3am.",
                "If the premium existed as a retention bonus last year, the travelers would be staff.",
            ),
            (
                ("rate-card", "They told me there was no money. Then the traveler's rate leaked. There was money."),
                ("3am-memory", "Nobody knows where the difficult airway cart lives. That is a staffing model."),
                ("stay-pay", "Match a third of the travel rate and I will stay. They would rather rent a stranger."),
            ),
        ),
        (
            "Closures",
            "Towns meet the crisis as a dark ER and a longer ambulance — obstetrics first, then everything else.",
            (
                "A labor-and-delivery closure is a population policy with a county name on it.",
                "Critical-access math that cannot survive a payer mix is a federal choice, not a local failure of virtue.",
                "Keeping the helipad after losing the OR is how you gamble with minutes.",
            ),
            (
                ("ob-gone", "Babies are a highway problem now. That used to be a hallway."),
                ("payer-mix", "We did not get worse at medicine. We got worse at being the wrong zip code."),
                ("helipad", "The helicopter is not a hospital. Stop selling it like one."),
            ),
        ),
        (
            "Ratios",
            "Nurses want a number in statute: patients per nurse as a safety spec, not a vibe the charge nurse has to beg for.",
            (
                "A ratio is a clinical device. 'Flexible staffing' is a budget device.",
                "When the hallway is a unit, the ratio already failed, whether the law noticed or not.",
                "If the board can find a building campaign, it can find the fourth nurse.",
            ),
            (
                ("hall-unit", "I had eight, two in chairs. The board had a rendering of a pavilion."),
                ("flex", "Flex means I eat lunch in a supply closet, or I do not eat."),
                ("statute", "Put the number in the law. I am tired of being the number."),
            ),
        ),
        (
            "Burnout",
            "This cluster names moral injury: not tiredness, but being asked to discharge a person into nowhere.",
            (
                "Burnout is what we say when we cannot say the staffing plan is unsafe and we still have to clock in.",
                "A resilience workshop is an insult when the assignment is impossible.",
                "People leave the bedside for a spreadsheet job because the spreadsheet does not die on their license.",
            ),
            (
                ("moral", "I did not burn out on hard work. I burned out on fake discharges."),
                ("workshop", "They gave us yoga and a fourth admission. I kept the admission."),
                ("spreadsheet", "I code now. Nobody codes at 4am because a ratio was a suggestion."),
            ),
        ),
    ),
    "Aging Care": faces(
        (
            "Nursing Homes",
            "Families describe the building as understaffed, over-regulated on paper, and one infection away from a lockout.",
            (
                "A ratio that exists in a binder and not on the night shift is how people get hurt.",
                "Private equity that extracts the real estate and leaves the care as a lease is a model, not a mystery.",
                "If the only people who will do the work are on a visa or a last nerve, the wage is the policy.",
            ),
            (
                ("night-two", "Two aides for 40. The state had a form. The form was not in the hallway."),
                ("propco", "They sold the building to themselves and called the rent a cost of care. Cute."),
                ("visa-wage", "Pay a wage a citizen can live on or admit the model needs a pipeline you will not name."),
            ),
        ),
        (
            "Medicare Gaps",
            "This view is the doughnut, the home-care cliff, and a dental mouth that is somehow not a body.",
            (
                "A program that pays for the hospital and shrugs at the mouth is not coverage. It is a specialty.",
                "The home-health episode ending while the person is still a person is the cliff families fall off.",
                "Observation status is a word trick that turns a stay into a bill.",
            ),
            (
                ("mouth", "Her teeth are why she cannot eat. Medicare would like a different organ."),
                ("episode-end", "The nurse vanished on day 61. The diagnosis did not."),
                ("observation", "Three nights on a gurney and it was not an admission. That is a spell, not a benefit."),
            ),
        ),
        (
            "Family Leave",
            "The sandwich generation wants time that is actually paid — not a brochure right to go broke beside a hospital bed.",
            (
                "Unpaid leave is a right for people with a spouse who already has a job and a savings account.",
                "A week of bereavement and a year of dying are not the same policy problem.",
                "If the largest long-term-care workforce is daughters, pay them or lose them from the other job.",
            ),
            (
                ("brochure-right", "I qualified. I could not afford it. That is not leave. That is a pamphlet."),
                ("year-dying", "Hospice is a philosophy. Someone still has to do Tuesday."),
                ("daughters", "The employment report does not see me. The hospital bed does."),
            ),
        ),
        (
            "Isolation",
            "A quieter cluster treats loneliness as a clinical risk: closed senior centers, vanished bus routes, and a tablet that is not a nephew.",
            (
                "A wellness check that is a screen is better than nothing and much worse than a room with coffee.",
                "Congregate meals are health care. Ending them to 'modernize' is a cut.",
                "Design that assumes a driver in the family will strand the people who most need the appointment.",
            ),
            (
                ("tablet-nephew", "The iPad is fine. It does not take her to the podiatrist."),
                ("congregate", "The lunch was the medicine. The freeze-dried replacement is a box."),
                ("no-bus", "They cut the Tuesday route. Tuesday was dialysis. Very efficient."),
            ),
        ),
    ),
    "Reproductive Care": faces(
        (
            "Clinic Access",
            "Patients describe miles, wait times, and a map that changed while the appointment did not wait.",
            (
                "A right that is a plane ticket is a right for people with a credit card and a boss who does not ask questions.",
                "Clinic closures are a health-system event. The OB shortage is the rhyme.",
                "If the nearest legal care is a state away, the wait is the ban.",
            ),
            (
                ("miles", "The appointment is legal. The Tuesday off is not. That is the access."),
                ("ob-desert", "They closed the clinic and then the labor ward. The map is the policy."),
                ("wait-is-ban", "Two weeks later is a different medicine. Clocks are the statute."),
            ),
        ),
        (
            "Medication",
            "This cluster is pills in the mail, pharmacies that refuse, and a protocol that outran the clinic building.",
            (
                "A pharmacy that will not fill a legal script is a second legislature.",
                "Telemed plus a mailbox is how people actually get care. Pretending it is a loophole is the tell.",
                "Shield laws and extradition threats are now part of a prescription. That is not how a refill should feel.",
            ),
            (
                ("counter", "The pharmacist had a feeling. My doctor had a license. Guess who won Tuesday."),
                ("mailbox", "Care arrived in a box. The building was a decoy. Fund the box."),
                ("shield", "I need a lawyer to send a tablet. That sentence should not exist in a formulary."),
            ),
        ),
        (
            "Travel",
            "Practical logistics: gas, childcare, a friend with a couch, and a state line that is now a clinical step.",
            (
                "Abortion funds are a health system. Treat the volunteers like one.",
                "A waiting period plus a 400-mile drive is not reflection. It is a means test.",
                "Employers and schools that punish the absence are enforcing the map.",
            ),
            (
                ("fund-venmo", "A stranger paid the hotel. That stranger is the Medicaid we actually have."),
                ("400-miles", "The waiting period assumed I lived across the street. I do not."),
                ("write-up", "I used a sick day and got a write-up. The policy is also my boss."),
            ),
        ),
        (
            "Employers",
            "HR as the new clinic: travel stipends, formularies, and a benefits PDF that depends on the ZIP of the headquarters.",
            (
                "A stipend is not a right. It is a perk that vanishes with the job.",
                "National companies are writing a patchwork health policy because legislatures did.",
                "If your coverage ends at the state line, you do not have coverage. You have a map.",
            ),
            (
                ("stipend-perk", "They will fly me once. They will not fight the statute. I noticed."),
                ("hq-zip", "Care depends on where the CEO sits. That is a wild way to run a formulary."),
                ("map-plan", "The SPD has a cartography appendix. I am not kidding."),
            ),
        ),
    ),
    "Addiction Policy": faces(
        (
            "Overdose",
            "This cluster is still the numbers: fentanyl in the supply, naloxone in the pocket, and a death that used to be a scare.",
            (
                "A supply that kills on the first mistake is not the crisis we trained for. The training has to move.",
                "Naloxone is a floor, not a treatment plan. Floors still matter.",
                "If the death is in a bathroom with no lock and no kit, design is the policy.",
            ),
            (
                ("first-mistake", "We used to get second chances. The powder ended that. Say it that way."),
                ("narcan-pocket", "I carry it like keys. That is not a solution. It is a truce."),
                ("bathroom", "Put a kit on the wall and stop locking people in to die politely."),
            ),
        ),
        (
            "Treatment Beds",
            "Families treat the waitlist as the actual statute: ready on Thursday, a bed in three weeks.",
            (
                "A person who asks for help on a weekday and waits is not noncompliant. The bed is.",
                "If detox is a hallway and MAT is a maze, the 'treatment on demand' speech is a brand.",
                "Cash facilities for the insured and a wait for everyone else is a caste system with a clinical smell.",
            ),
            (
                ("thursday", "He was willing on Thursday. The bed was in June. June did not get him."),
                ("mat-maze", "The clinic is 90 minutes and a urine cup. That is not on demand. That is an obstacle course."),
                ("cash-bed", "The nice place took a card. The public place took a number. Guess which census we count."),
            ),
        ),
        (
            "Safe Supply",
            "A smaller group wants a regulated alternative to a poisoned street — controversial, and they know it.",
            (
                "If the street is a roulette wheel, a clinic-grade option is harm reduction with a chemist, not a slogan.",
                "Diversion risk is real. So is a death count that does not care about our discomfort.",
                "Pilot it, measure it, publish it. Moral panic is not a trial design.",
            ),
            (
                ("roulette", "I would rather him on a weighed dose than a mystery stamp. Judge me after the funeral you do not have to attend."),
                ("divert", "Yes, some will leak. Some already die. I can do both numbers."),
                ("pilot", "Run the trial. If it fails, it fails in public. The street is already a trial with no IRB."),
            ),
        ),
        (
            "Courts",
            "Drug courts, mandatory treatment, and a prosecutor who is still the intake office.",
            (
                "A court cannot be the front door to medicine without becoming a worse hospital.",
                "Coerced treatment that has no treatment attached is just a longer sentence.",
                "If the charge is possession of a death-trap supply, the punishment will not unpoison the next bag.",
            ),
            (
                ("front-door", "He met a judge before he met a doctor. That sequence is the system."),
                ("coerced-empty", "The order said treatment. The county said waitlist. The violation said jail."),
                ("next-bag", "Lock the person. The stamp still wins. I would like a policy about the stamp."),
            ),
        ),
    ),
    "Disability Access": faces(
        (
            "Transit",
            "Riders describe paratransit windows, broken elevators, and a bus that kneels in theory.",
            (
                "A 4-hour pickup window is not transit. It is house arrest with a van.",
                "Elevators out of service with no date are how a system announces who may travel.",
                "If the app cannot book a wheelchair space, the app is the barrier.",
            ),
            (
                ("window", "They gave me 7 to 11. My appointment is at 8. That is not a ride. That is a shrug."),
                ("elevator", "Three stations, three outages, one city that loves a press release about inclusion."),
                ("app-space", "I can tap pay. I cannot tap a space that exists. Fix the software or admit the fleet."),
            ),
        ),
        (
            "Workplaces",
            "This cluster wants accommodations that are not a negotiation with a stranger in HR who has a mood.",
            (
                "A process that takes three months is a no that learned to speak politely.",
                "Remote as an accommodation vanished when the badge policy returned. That was a tell.",
                "If the job can be done with a screen reader, the PDF that cannot is the violation.",
            ),
            (
                ("three-months", "The job ended before the chair arrived. Very agile."),
                ("badge-back", "They discovered my disability the day they discovered the office. I noticed."),
                ("pdf-wall", "The application was a picture of text. That is not a portal. That is a locked door."),
            ),
        ),
        (
            "Benefits Cliffs",
            "People on SSI/SSDI treat a raise, a marriage, or a savings account as a trap the brochure calls an incentive.",
            (
                "A $1 job that costs $4 in benefits is not a ladder. It is a punishment for trying.",
                "Asset limits from another century are how you keep people poor on purpose.",
                "If work is the goal, the phase-out has to look like a ramp, not a cliff you need a lawyer to see.",
            ),
            (
                ("dollar-trap", "I got hours. I lost the aide. The hours cannot replace the aide. Do the math they will not print."),
                ("asset-1980", "I cannot save for a tire. That is not fraud prevention. That is a cage."),
                ("ramp", "Draw me a phase-out a human can ride. I can work. I cannot teleport."),
            ),
        ),
        (
            "Devices",
            "Wheelchairs, hearing aids, and DME as a prior-auth novel — equipment that is medicine and is treated as a luxury SKU.",
            (
                "A chair that takes 11 months is a sentence to the bed.",
                "Hearing aids on a consumer price tag while glasses sit in a drugstore is a caste of the senses.",
                "Repair rights for a wheelchair should not be rarer than repair rights for a tractor.",
            ),
            (
                ("11-months", "I grew around a broken frame waiting for a 'custom' that is a catalog. Time is the denial."),
                ("hearing-sku", "My ears are retail. My neighbor's lenses are a kiosk. Explain it without the word lifestyle."),
                ("right-to-fix", "The vendor has the key. My mechanic does not. I am not a printer."),
            ),
        ),
    ),
    "Pandemic Memory": faces(
        (
            "Long Covid",
            "Patients treat the after as the event: PEM, stalled careers, and a clinic that still says anxiety first.",
            (
                "A mass disabling event that we filed under 'over' is how you get a workforce surprise.",
                "If the test is normal and the person cannot stand, believe the person while you build the test.",
                "Workplaces that only understand broken bones will keep firing people with a new disease.",
            ),
            (
                ("pem", "I can do the meeting or the dishes. Not both. That is not anxiety. That is a budget of energy."),
                ("normal-labs", "The labs are pretty. I am not. Update the algorithm."),
                ("fired-quietly", "They called it attendance. It was a disease they were bored of."),
            ),
        ),
        (
            "School Years",
            "Parents and teachers are still in the unfinished learning, the social lag, and a fight about whether any of it was worth it.",
            (
                "The kids who lost a year of decoding did not lose a vibe. They lost a sequence that does not replay itself.",
                "We can argue the closures and still fund the tutoring. Both can be serious.",
                "Attendance that never came back is a public-health hangover, not a character flaw.",
            ),
            (
                ("sequence", "Third grade is not optional. We treated it like a streaming season they could catch up."),
                ("tutor-anyway", "I can be angry at 2020 and still want a person at the table three times a week."),
                ("ghost-roll", "They did not return. We called it choice. Some of it is fear that never got a clinic."),
            ),
        ),
        (
            "Trust",
            "This cluster is the scar: agencies that overpromised, under-explained, and then asked to be believed about the next thing.",
            (
                "A guidance flip without showing the data is how you train people to ignore the next guidance.",
                "If you mocked cloth, then mandated cloth, then shrugged, you are why the measles rate is a live issue.",
                "Trust is a reservoir. You cannot pump it dry for a year and then demand a high water mark.",
            ),
            (
                ("flip", "I can live with new evidence. I cannot live with a vibe that I am stupid for remembering last month."),
                ("measles", "The hangover is not COVID. The hangover is every shot we still need."),
                ("reservoir", "They spent the trust on a press conference. The next pathogen will send a bill."),
            ),
        ),
        (
            "Stockpiles",
            "A logistical minority wants the boring lesson: PPE, antivirals, and a factory that can exist in peacetime.",
            (
                "A stockpile that expired in a warehouse is a press release from a previous mayor.",
                "Just-in-time for masks is how a nation auctions surgical gear on a group chat.",
                "If the lesson was industrial base, the appropriation should look like one, not a monument.",
            ),
            (
                ("expired", "We had a pile. Then we had dust. Then we had a GoFundMe for gowns."),
                ("group-chat", "Procurement was a text thread. I would like a contract instead."),
                ("base", "Pay a factory to idle on purpose. Insurance is supposed to look wasteful."),
            ),
        ),
    ),
    "Food Systems": faces(
        (
            "Ultra-processed",
            "This view treats the aisle as an industrial product: cheap calories engineered to outcompete a kitchen.",
            (
                "If the food is cheaper than the ingredients, the subsidy is the recipe.",
                "Personal responsibility in a desert of 19-ingredient snacks is a sermon, not a diet.",
                "A warning label is not a farm bill. The farm bill is the diet.",
            ),
            (
                ("cheaper", "The bag is $1.19. The fruit is a luxury. That is not my character. That is a price."),
                ("desert", "The nearest vegetable is a gas station. Lecture me after the bus."),
                ("farm-bill", "We grow the inputs to the bag. Stop pretending the bag is a surprise."),
            ),
        ),
        (
            "School Meals",
            "Advocates want the cafeteria as the equalizer: universal, actually edible, and not a debt collector for a child's lunch.",
            (
                "A lunch shaming policy is a nutrition policy. It just aims at humiliation.",
                "Universal meals are logistics. Means tests are how you miss the kid who almost qualifies.",
                "If the kitchen cannot cook, the contract is the curriculum.",
            ),
            (
                ("debt-letter", "They mailed a third-grader's balance. That is the wellness plan."),
                ("universal", "Just feed them. The paperwork costs more than the extra trays."),
                ("heat-and-serve", "We outsourced the kitchen and imported the sodium. Very modern."),
            ),
        ),
        (
            "Farm Workers",
            "The people who pick the aisle still show up as heat, piece rates, and a visa that is a leash.",
            (
                "A food system that cannot survive a shade-and-water rule is not efficient. It is extractive.",
                "H-2A that ties a person to one boss is a labor market with a fence.",
                "If the berry is cheap, look at the body that moved it. That is the true unit price.",
            ),
            (
                ("heat-index", "We got a new app for the heat. We did not get a later start. The app is not shade."),
                ("leash", "The visa is the boss. OSHA is a poster in a language the boss does not speak."),
                ("unit-price", "Your cheap pint is a medical bill in July. I have seen both invoices."),
            ),
        ),
        (
            "Price",
            "Households still live in the receipt: meat, milk, and a 'shrink' that is a raise for the processor.",
            (
                "Food-at-home inflation is a political fact whether the print cooled or not.",
                "A concentrated packer that takes a cut in a drought is not weather.",
                "SNAP that lags the aisle by months is a hunger policy with a COLA hobby.",
            ),
            (
                ("receipt", "The print cooled. The chicken did not. I vote with the chicken."),
                ("packer", "Cattle are cheap. Beef is not. Someone in the middle is having a year."),
                ("snap-lag", "Benefits are last year's aisle. Kids eat this week's."),
            ),
        ),
    ),
    "Sleep Crisis": faces(
        (
            "Shift Work",
            "Nights, rotating shifts, and a body that is asked to be two species.",
            (
                "A rotating shift is a medical exposure. Pretending it is a preference is how you skip the premium.",
                "If the hospital can schedule the same nurse nights-to-days in 24 hours, the schedule is the incident report.",
                "Gig nights plus a day job is two clocks and no sleep. That is a labor market, not a wellness gap.",
            ),
            (
                ("rotate", "I am a different animal every third day. OSHA has a poster. My heart has a shift."),
                ("clopen", "Close at 11, open at 5. That is not a shift. That is a dare."),
                ("two-clocks", "Warehouse at 4am, deliveries at 6pm. Sleep is the unpaid job."),
            ),
        ),
        (
            "Screens",
            "This cluster still points at the rectangle: late light, infinite scroll, and a childhood that does not night-sign off.",
            (
                "A device that profits from one more minute will not volunteer a bedtime.",
                "School-issued tablets that ping at 10pm are a district sleep policy.",
                "Blue light is a piece. The slot-machine feed is the piece that actually wins.",
            ),
            (
                ("one-more", "The app does not want me to sleep. That is not a glitch. That is the quarter."),
                ("10pm-ping", "Homework notified her at 10:12. The district is the insomnia."),
                ("slot", "I can dim the screen. I cannot dim the next video. Design is the drug."),
            ),
        ),
        (
            "Clinics",
            "Apnea, insomnia meds, and a sleep lab that is a four-month wait — medicine catching up to a culture that will not lie down.",
            (
                "A CPAP that takes six prior-auth letters is a treatment we do not mean.",
                "Prescribing a knockout instead of a schedule is how you get a second problem.",
                "If the lab wait is a season, home testing should be the default, not a fight.",
            ),
            (
                ("auth-cpap", "My breathing lost to a form. The form is very thorough."),
                ("knockout", "They gave me a pill because the boss would not give me a shift. Cute diagnosis."),
                ("home-study", "I can wear a watch. I cannot wait until Q3 to find out I stop breathing."),
            ),
        ),
        (
            "Kids",
            "Parents want later start times, earlier dark, and a sport culture that does not own 9pm.",
            (
                "A 7:20 bell for a teenager is a biological own-goal the bus schedule pretends is character.",
                "Travel ball that ends at 9:30 on a school night is a sleep intervention with a fee.",
                "Phones in bedrooms are a parenting fight the product was built to win.",
            ),
            (
                ("7-20", "We know the science. We also know the elementary bus. The bus won."),
                ("9-30-ball", "Championship character, they said. The quiz tomorrow disagrees."),
                ("charger-hall", "The hallway charger is the only product change that worked. The app did not help me."),
            ),
        ),
    ),
    "Longevity Hype": faces(
        (
            "Supplements",
            "A noisy market of powders that outrun the evidence and under-run the label.",
            (
                "If the claim were a drug, it would need a trial. The powder would like the revenue without the trial.",
                "A stack that costs more than groceries is a class hobby, not a public-health plan.",
                "Heavy metals in a 'longevity' tub is the unfunny version of optimization.",
            ),
            (
                ("not-a-drug", "They cited a mouse and charged me like a clinic. I would like a human."),
                ("grocery-stack", "My NMN costs more than my produce. That is not health. That is a store."),
                ("metals", "The independent test was the only adult in the room. The brand was a vibe."),
            ),
        ),
        (
            "Biohackers",
            "Wearables, n=1 experiments, and a confidence that the PCP's 12 minutes cannot match.",
            (
                "A dashboard is not a diagnosis. It is a mood with a heart-rate line.",
                "People hacking sleep while ignoring shift work are optimizing the wrong variable.",
                "The useful part is curiosity. The dangerous part is a protocol that skipped the control.",
            ),
            (
                ("dashboard", "My whoop thinks I am thriving. My labs think I should call someone. I called the labs."),
                ("wrong-var", "I optimized caffeine and ignored the 12-hour shift. The shift won."),
                ("n-1", "I am the trial, the sponsor, and the adverse event. Cute IRB."),
            ),
        ),
        (
            "Clinic Tourism",
            "Infusion rooms, stem-cell weekends, and a passport that is the actual informed consent.",
            (
                "A clinic that cannot exist next to an FDA field office is telling you the risk.",
                "Paying cash to skip evidence is how you fund the next injury without a registry.",
                "If it worked like the ad, it would be a specialty, not a concierge.",
            ),
            (
                ("passport", "The brochure had a beach. The consent had an airline. I noticed."),
                ("no-registry", "When it goes wrong, there is no database. That is the product feature."),
                ("specialty", "Show me the residency. Then take my card. Until then it is a spa with a needle."),
            ),
        ),
        (
            "Evidence",
            "Clinicians want the boring stack: trials, all-cause mortality, and a skepticism of biomarkers that make pretty charts.",
            (
                "A marker that moves and a life that does not is how you sell a subscription.",
                "Aging is not a deficiency of a brand's molecule. It is a process. Humble the claim.",
                "If the endpoint is a selfie, it is not gerontology. It is marketing.",
            ),
            (
                ("marker", "My CRP is a personality. My stairs are the outcome. Fund the stairs."),
                ("humble", "I will take exercise, sleep, and blood pressure before I take a god complex in a vial."),
                ("selfie-end", "The paper is a thread. The thread is a before-and-after. Sit down."),
            ),
        ),
    ),
}
