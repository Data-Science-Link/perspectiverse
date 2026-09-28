"""Technology extras beyond AI Futures and Digital Privacy."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Platform Power": faces(
        (
            "App Bans",
            "This cluster treats storefront removals and national bans as political weapons that users cannot appeal, not as safety hygiene.",
            (
                "When a government or a storefront can zero an app overnight, speech and livelihood sit behind a terms-of-service cop.",
                "Safety claims that never come with a public evidence room are just a takedown with better lighting.",
                "A ban that leaves the same content on a dozen clones is theater. It trains people to expect disappearance, not due process.",
            ),
            (
                ("sideload-mom", "They banned the app my cousin uses to call home and left the clones. That is not safety. That is a press conference."),
                ("dev-gone", "My game vanished on a Friday with a template email. Support is a form that thanks me for my patience."),
                ("shop-cop", "If the store can unperson a newsroom, it is a regulator. Bill it like one."),
            ),
        ),
        (
            "Store Fees",
            "Developers argue that 15–30% plus mandatory billing is a tax on software, extracted because the door is the product.",
            (
                "A toll on every subscription is not 'keeping the ecosystem safe'. It is rent on the only door users are allowed to use.",
                "Small studios pay the same cut as mega-publishers and eat it in slow death, not in a keynote.",
                "If sideloading and competing billing are dangerous, the danger is competition.",
            ),
            (
                ("indie-sub", "Thirty percent of a $4 membership is my rent. Apple did not write the levels."),
                ("web-pay", "We added a web checkout and got a scary review. Safety, they said. The invoice said otherwise."),
                ("store-tax", "Call it a commission when there is another register. This is a border tariff on bits."),
            ),
        ),
        (
            "Moderation",
            "Users and workers describe trust-and-safety as an invisible legislature: inconsistent, understaffed, and allergic to appeals.",
            (
                "A rule that cannot be quoted, only felt, is not a rule. It is a mood with a strike system.",
                "Outsourcing the worst queue to contractors and then blaming 'the algorithm' is how platforms keep their hands clean.",
                "Appeals that take weeks teach people to pre-censor. That is the point, whether anyone wrote it down or not.",
            ),
            (
                ("strike-3", "I lost a year of photos to a spam classifier. The appeal was a checkbox. The checkbox lost."),
                ("queue-night", "We are the legislature at $18 an hour. Legal wants speed. Users want Solomon. We have a rubric."),
                ("context-bot", "Satire, news, and gore look the same to a model that has never been to our town."),
            ),
        ),
        (
            "Antitrust",
            "This view says the platforms are infrastructure, and that merger-and-default cases are how you get a public square that is not a company town.",
            (
                "When search, ads, mobile, and cloud are the same firm, 'choice' is a settings page nobody finds.",
                "Default placement is the product. Everything else is a hobby app.",
                "Breakups are messy. Monopoly pricing and copycat kill-zones are messier, just quieter.",
            ),
            (
                ("default-bar", "The browser I want is three menus down. That is not a market. That is furniture."),
                ("kill-zone", "They cloned our feature, bundled it free, and took the meeting that used to be ours."),
                ("ads-stack", "The auction is the tax. The tax funds the default. The default funds the auction. Cute."),
            ),
        ),
        (
            "Creator Cuts",
            "Creators treat ranking changes and revenue splits as wage-setting by a boss who will not admit to employing them.",
            (
                "If the feed can zero your income overnight, you are not a small business. You are a contractor with a mood ring.",
                "A 45-second 'boost' that expires unless you post daily is a time clock, not a community.",
                "Transparency on RPM and reach is the minimum. 'Just make better content' is HR copy.",
            ),
            (
                ("rpm-drop", "Same audience, half the pay, new 'originality' score. That is a pay cut. Say it."),
                ("daily-clock", "The algorithm wants a streak. My kid wants dinner. Guess which one the mortgage hears."),
                ("brand-safe", "They demonetized a news clip for 'sensitive events'. The events were the job."),
            ),
        ),
    ),
    "Chip Race": faces(
        (
            "Export Controls",
            "Policy people treat GPU and tool bans as the actual industrial strategy — slow the rival, accept the blowback.",
            (
                "If the frontier is compute, then shipping the best accelerators is a weapons-export question, not a sales one.",
                "Controls leak through allies, cloud access, and last-generation silicon. Pretending otherwise is a press kit.",
                "A ban without a domestic buildout is a pause button, not a strategy.",
            ),
            (
                ("gpu-wait", "We cannot buy the card the lab next door rents by the hour in another country. That is the policy working, I guess."),
                ("foundry-note", "Export control without a fab is a sermon. The wafer still has to exist somewhere."),
                ("cloud-loophole", "They cannot import the box. They can rent it. Geography is a billing address."),
            ),
        ),
        (
            "Fab Jobs",
            "This cluster wants the CHIPS money to show up as apprenticeships, housing, and a shift that a technician can actually live on.",
            (
                "A ribbon-cutting is not a workforce. Clean-room techs need training seats and a rent they can pay.",
                "Importing the entire skilled crew and calling it a regional win is a press release with a per diem.",
                "If the plant needs power, water, and a high school that can do math, fund those like they are part of the fab.",
            ),
            (
                ("shift-2", "The wage is fine until you see the rent the announcement created. We built a boomtown without houses."),
                ("cc-cleanroom", "Put the community college inside the fence. Stop flying in every lead tech."),
                ("water-town", "They promised jobs. They also promised not to dry out the aquifer. The second slide was quieter."),
            ),
        ),
        (
            "Taiwan Risk",
            "A grim thread treats a single island's foundries as the world's most important single point of failure.",
            (
                "Concentration that made chips cheap also made a blockade a civilization-scale shortage.",
                "Friendly-shore fabs are insurance. Insurance is supposed to look redundant and slightly wasteful.",
                "Talking around the geography does not make the geography less real.",
            ),
            (
                ("solder-map", "My BOM has one island in it, over and over. That is not a supply chain. That is a prayer."),
                ("wargame", "We run the tabletop and the answer is always 'hope the ships still move'. I would like a second answer."),
                ("inventory", "Everyone 'diversified' by adding a second OSAT in the same strait. Cute."),
            ),
        ),
        (
            "Consumer Prices",
            "Buyers and repair shops say the race shows up as GPUs, cars, and consoles that are luxury goods with a waitlist.",
            (
                "When training clusters eat the top silicon, the gaming card and the clinic imager wait in the same line.",
                "MSRP is a rumor. Street price is the industrial policy landing on a paycheck.",
                "Right to repair dies when the board is a black box and the spare is on allocation.",
            ),
            (
                ("stock-drop", "The 80-series is a lottery. Scalpers and data centers got there first. I just wanted a machine that compiles."),
                ("clinic-img", "Our scanner board is on a six-month lead. Someone's model is using that fab time to write poems."),
                ("repair-bay", "No spare SoC, no salvage board. Planned scarcity with a better story."),
            ),
        ),
    ),
    "Open Source": faces(
        (
            "Maintainer Burnout",
            "Maintainers describe popular infrastructure as an unpaid on-call job with strangers filing emergencies in the dark.",
            (
                "A library that runs the internet and a single volunteer on a Sunday is not a commons. It is a hostage situation.",
                "GitHub stars are not staffing. Neither are 'just one small PR' comments from companies that will not hire you.",
                "Burnout is the security bug. Exhausted people merge worse, or they walk.",
            ),
            (
                ("dep-sunday", "I am the author of a package with 40 million downloads and a day job. Your CVE can wait until Monday or you can pay."),
                ("nudge", "A FAANG bot thanked me for my service and assigned me a sev-1. I closed the tab."),
                ("archive-it", "I archived the repo. That is the only boundary the license actually gave me."),
            ),
        ),
        (
            "Corporate Capture",
            "This view says big vendors harvest the commons, relicense the juicy parts, and leave issues on the public tracker.",
            (
                "Open washing is a marketing strategy: screenshot the GitHub org, keep the roadmap behind a CLA.",
                "When the largest committers are on one payroll, 'community governance' is a mailing list with a boss.",
                "Extracting value and returning issues is not a partnership. It is a strip mine with a CoC.",
            ),
            (
                ("cla-wall", "They want my copyright and my nights. In return I get a sticker and a seat without a vote."),
                ("relicense", "The cloud giant took the code SSPL and called it giving back. The giving was the trademark."),
                ("issue-bot", "Corporate filers outnumber the people who can close. That is capture by volume."),
            ),
        ),
        (
            "License Fights",
            "A legalistic cluster treats AGPL, SSPL, and 'open core' as the actual politics: who may wrap the code in a meter.",
            (
                "Permissive licenses socialized the work and privatized the rent. Copyleft is the attempt to name that.",
                "Fair-use for models trained on repos is the next license fight, whether the OSI wants it or not.",
                "If your business model is someone else's LICENSE file, you should expect the file to change.",
            ),
            (
                ("agpl-fan", "I ship AGPL because I have seen what Apache bought us: a hosted clone and a smile."),
                ("osi-thread", "They spent a month arguing whether a word is 'open'. Users spent it patching."),
                ("train-on-us", "Your model memorized my repo. The MIT license did not mean 'become my unpaid dataset'."),
            ),
        ),
        (
            "Security Holes",
            "This cluster treats unmaintained dependencies as the real attack surface — a commons that nobody is paid to patch.",
            (
                "A 2013 library in a 2026 binary is not a skill issue. It is an economy that does not fund the floor.",
                "SBOM theater without a person who can bump the pin is a PDF. Attackers do not read PDFs.",
                "Critical infrastructure running 'community-supported' crypto is a national-security hobby.",
            ),
            (
                ("cve-bot", "The scanner found 40 highs. 39 of them are in a package whose author is a ghost. Now what."),
                ("pin-from-hell", "We cannot upgrade: the next minor breaks a vendor SDK that will not move. That is the hole."),
                ("log4-memory", "We all swore after the last one. Then we staffed the same way. Hope is not a control."),
            ),
        ),
    ),
    "Cyber Attacks": faces(
        (
            "Ransomware",
            "Operators and victims treat encryption-for-extortion as a business model that found the unpatched district and the unpaid IT shop.",
            (
                "Paying is how you buy the next attack. Not paying is how you buy a month of paper. Both are true.",
                "Backups that have never been restored are a comfort object. The gang already knows which towns have them.",
                "A school district is not a soft target. It is a target with a weak password and a public board agenda.",
            ),
            (
                ("restore-fail", "The backups restored into the same malware. We had a ritual, not a plan."),
                ("city-fax", "Payroll went to paper for three weeks. The gang knew our insurance better than our CIO did."),
                ("patch-tue", "They asked for a new SIEM. They needed someone to click yes on last October's updates."),
            ),
        ),
        (
            "Hospital Hits",
            "Clinicians describe diverted ambulances and paper charts as the human end of a stolen VPN credential.",
            (
                "When the EHR is a brick, care becomes memory, handwriting, and delay — and delay is a clinical harm.",
                "A hospital is a factory of life-support machines on a network that still has a default password in a closet.",
                "Cyber is now a patient-safety committee item, not an IT inconvenience.",
            ),
            (
                ("er-divert", "We diverted strokes for six hours because the CT could not talk to the record. That is a body count with a phishing email."),
                ("paper-mar", "I wrote meds on a paper towel. I am a pharmacist, not a Civil War reenactor."),
                ("vpn-default", "The entry was a vendor fob that nobody rotated. The ransom note was just the invoice."),
            ),
        ),
        (
            "State Actors",
            "A harder cluster talks about APTs, cable taps, and pre-positioning — crime with a flag, not a teenager in a hoodie.",
            (
                "If the point is to sit in the grid until a political moment, ransomware is the noisy cousin, not the main event.",
                "Attribution is slow on purpose. The patch cannot wait for a press conference.",
                "Hospitals, water, and software updates are dual-use now. Treat them like that in the budget.",
            ),
            (
                ("quiet-grid", "They did not encrypt us. They lived in the historian for a year. Ransomware would have been a relief."),
                ("update-path", "The interesting attack is the one that signs in as your vendor. Flags do not show in the syslog."),
                ("cable-map", "We talk about apps. They talk about landing stations. Different war."),
            ),
        ),
        (
            "Password Fatigue",
            "Users treat MFA fatigue, password managers, and recovery hell as the everyday security story that actually decides who gets owned.",
            (
                "A 40-character policy and a sticky note is not a control. It is a dare.",
                "Push-bombing is what you get when 'something you have' is a tired thumb.",
                "Account recovery is the real authentication system, and it is usually a birthday and an inbox.",
            ),
            (
                ("sticky-note", "Reset it every 60 days and people will write it on the monitor. We measured this. We did it anyway."),
                ("push-yes", "I approved a prompt at 2am because they sent twenty. That is not user error. That is a broken factor."),
                ("grandma-inbox", "Her recovery is the email she lost in 2019. The bank still thinks that is identity."),
            ),
        ),
    ),
    "Smart Cities": faces(
        (
            "Sensor Streets",
            "Residents argue that cameras, mics, and plate readers turned the block into a product, with a vendor dashboard for a city hall.",
            (
                "A pole that hears gunshots and also stores faces is not a public safety tool until the retention policy is a law.",
                "Consent is a joke when the alternative is not using the sidewalk.",
                "If the feed can be subpoenaed, sold, or breached, it is a public records problem wearing an LED.",
            ),
            (
                ("pole-cam", "There are four cameras on my corner and no bus shelter. That is a budget with a lens."),
                ("shotspotter", "The mic is sure. The cops are late. We bought a siren, not a solution."),
                ("plate-lot", "They know I was at the clinic. The city calls it traffic. I call it a file."),
            ),
        ),
        (
            "Vendor Lock-in",
            "Procurement people describe 'smart' as a 15-year contract that outlives the mayor and the API.",
            (
                "A city that cannot export its own traffic data does not own a system. It is renting a mayor's dashboard.",
                "Closed protocols on streetlights are how a lighting bid becomes a surveillance monopoly.",
                "If the only people who can change a timing plan work for the vendor, democracy has an SLA.",
            ),
            (
                ("api-wall", "We asked for the data. They offered a PDF. That is not a partner. That is a hostage-taker with a logo."),
                ("light-bus", "The bulbs are fine. The software lease is the streetlight now."),
                ("rfp-ghost", "Nobody else bid because the spec was written in the incumbent's dialect. Cute."),
            ),
        ),
        (
            "Traffic AI",
            "This cluster wants signals that actually move buses and ambulances, and is tired of a 'digital twin' that cannot fix a left turn.",
            (
                "Optimization that does not count people on the bus is just speeding up cars.",
                "A model trained on last year's congestion will freeze a bad geometry in place and call it intelligence.",
                "Give the emergency preemption and the bus a real priority. The rest is a demo day.",
            ),
            (
                ("bus-red", "The 'smart' corridor made the car two minutes faster and the bus four minutes slower. Check the weights."),
                ("twin-town", "They showed a 3D model of the intersection. The left-turn arrow is still a myth at 5pm."),
                ("emt-preempt", "If the software cannot see a siren, it is not AI. It is a timer with a press kit."),
            ),
        ),
        (
            "Public Records",
            "Journalists and residents want the logs, contracts, and retention schedules — the unsexy half of a camera network.",
            (
                "A smart city that cannot answer a FOIA is not modern. It is a black box with a tourism video.",
                "Retention is the policy. Without it, every sensor is a forever archive waiting for a later use.",
                "Publish the contracts. If the clause says the vendor owns the footage, the city sold the sidewalk.",
            ),
            (
                ("foia-delay", "I asked for the retention schedule. They sent a marketing one-pager. That is the tell."),
                ("forever-clip", "There is no deletion date in the contract. So there is no deletion date on my kid's walk to school."),
                ("vendor-owns", "Clause 14: footage is the contractor's IP. We are the set. They are the studio."),
            ),
        ),
    ),
    "Biotech Tools": faces(
        (
            "Gene Editing",
            "This cluster treats CRISPR as a manufacturing method now — powerful, cheapening, and racing ahead of the clinic's ethics board.",
            (
                "A tool that can rewrite a germline is not 'just biology'. It is an industrial process with inheritance attached.",
                "Somatic therapies that work will create a politics of who can afford a one-time edit.",
                "Ban theater at the border will not stop a well-funded lab. Publish the rules where the work actually happens.",
            ),
            (
                ("bench-note", "The protocol is on a wiki and the enzyme is in the catalog. The bottleneck is courage, not equipment."),
                ("payer-edit", "A one-and-done cure that costs a mortgage is a miracle with a prior auth."),
                ("summit-ban", "They banned it in a communiqué and funded it in a rider. That is the real governance."),
            ),
        ),
        (
            "Lab Access",
            "Tinkerers and biosecurity people fight over garage labs: the same openness that spreads diagnostics can spread mistakes.",
            (
                "Democratized protocols without democratized waste handling is how you get a clever accident.",
                "Gatekeeping reagents can slow a fool. It also slows the clinic in a town the company does not care about.",
                "The right control is audited training and culture, not a romance about who is allowed to own a pipette.",
            ),
            (
                ("garage-pcr", "We ran wastewater tests in a warehouse and beat the official dashboard by a week. Access is a public good."),
                ("select-agent", "The interesting risk is not a movie virus. It is a competent person having a bad year."),
                ("mail-order", "If the kit ships, the policy shipped. Pretending otherwise is a vibe."),
            ),
        ),
        (
            "Patent Thickets",
            "Researchers describe stacked claims as the reason a test or a therapy dies in a lawyer's inbox, not in a trial.",
            (
                "A diagnostic that requires three licenses is not innovation. It is a toll booth with a journal citation.",
                "University tech-transfer offices that sit on tools are not stewards. They are landlords of a grant.",
                "Compulsory licensing talk shows up when a pandemic makes the thicket visible. The thicket was always there.",
            ),
            (
                ("freedom-op", "We designed around three patents and into a fourth. The molecule was the easy part."),
                ("tlo-shelf", "The campus owns a CRISPR tweak nobody can sublicense. That is a trophy, not a therapy."),
                ("test-toll", "The assay would cost $8 in reagents and $200 in letters. Guess which price the patient sees."),
            ),
        ),
        (
            "Clinic Ethics",
            "Clinicians want consent, equity, and off-label hype treated as the actual bottleneck once the tool works on paper.",
            (
                "A trial that only enrolls the already-insured will write a future that looks like the present, only more expensive.",
                "Informed consent is a process, not a PDF, especially when the edit is irreversible.",
                "Influencer clinics selling unproven infusions are the gray market the journal articles pretend not to see.",
            ),
            (
                ("consent-hour", "We spent more time on the form than on the science. That is not bureaucracy. That is the medicine."),
                ("enroll-gap", "The trial is 'open'. The travel stipend is not. Diversity died in the parking garage."),
                ("infusion-ad", "A clinic in a mall is selling youth. The FDA letter will arrive after the invoices."),
            ),
        ),
    ),
    "Space Industry": faces(
        (
            "Launch Cadence",
            "Boosters as buses is the new common sense: fly often, fail sometimes, treat orbit as a freight business.",
            (
                "Cadence is the product. A beautiful rocket that ships twice a year is a parade.",
                "Reuse only counts if the turnaround is weeks, not a refurbishment novel.",
                "National pride that cannot get a weather satellite up is just a museum with a countdown clock.",
            ),
            (
                ("pad-flow", "They flew again before my press embargo expired. That is the story. The paint job is not."),
                ("refurb", "If it needs a clean room and a priest, it is not reusable. It is a vintage car."),
                ("rideshare", "My cubesat finally rode. The bill of lading was more honest than the flag on the fairing."),
            ),
        ),
        (
            "Debris",
            "Operators treat junk, mega-constellations, and un-deorbited stages as a tragedy of the commons with closing speeds.",
            (
                "Kessler is not a vibe. It is a probability that gets worse every time someone leaves a stage in a popular orbit.",
                "A constellation that cannot deorbit on schedule is a landfill with a FCC filing.",
                "Space traffic management without teeth is an email list. Closing speeds do not RSVP.",
            ),
            (
                ("conjunction", "I got three collision alerts before coffee. That is not 'the future of connectivity'. That is a junkyard."),
                ("stage-left", "They called it a successful insertion. The upper stage is now a 7km/s lawsuit."),
                ("fcc-paper", "The deorbit plan is a PDF. The satellite is aluminum. Guess which one stays."),
            ),
        ),
        (
            "Moon Contracts",
            "This view reads Artemis and rival flags as an industrial policy: landers, power, and a legal theory about who may dig.",
            (
                "A moon base is a logistics problem that will be won by whoever can land watts and spare parts, not speeches.",
                "Mining rights without a dump and a labor rule is a brochure for lawyers.",
                "If NASA is the anchor tenant, the contractors are the city. Watch the task orders, not the logo.",
            ),
            (
                ("hls-slip", "The lander slipped again. The flag did not. Flags are cheap."),
                ("watts-on-regolith", "Power first, science second, tweets never. That is a base. The rest is a montage."),
                ("task-order", "Read the IDIQ. That is the actual space program."),
            ),
        ),
        (
            "Tourism",
            "Critics treat suborbital joyrides as carbon and spectacle, while a smaller group calls paying passengers the subsidy that funds the freight.",
            (
                "A ten-minute view for a hedge-fund ticket is not exploration. It is a very tall amusement park.",
                "If tourism cross-subsidizes launch cadence, say that. Do not call it a science mission.",
                "Safety culture that has to smile for a livestream will eventually choose the camera over the hold.",
            ),
            (
                ("joyride", "They sold weightlessness as meaning. It is a parabola with merch."),
                ("cadence-cash", "I do not love the billionaires. I love that their tickets paid for my weather bird."),
                ("hold-go", "The stream was live. The abort was late. Those two facts belong in the same sentence."),
            ),
        ),
    ),
    "App Stores": faces(
        (
            "Sideloading",
            "This cluster wants the phone to be a computer again: install a trusted binary without a mall cop at the gate.",
            (
                "A device that will not run software you trust is a rental, even if you paid the sticker.",
                "Malware is real. So is a single company deciding which newspaper may have an app.",
                "Sideloading with ugly warnings is still freedom. A grayed-out button is not.",
            ),
            (
                ("alt-store", "I installed the store that is not the Store. The phone asked me if I was sure five times. I was."),
                ("webapp-cage", "They broke PWAs the same week the law landed. Accidental, I am sure."),
                ("dev-sign", "Let me sign my own build for my own device. That used to be called owning a computer."),
            ),
        ),
        (
            "Teen Safety",
            "Parents want defaults that assume a child — age, time limits, and a store that does not upsell a slot machine.",
            (
                "A 12-year-old in an unfiltered storefront is not a user. They are inventory with a birthday.",
                "Age gates that are a checkbox are a gift to lawyers, not to families.",
                "Safety that only works if a parent is a sysadmin will fail the kids whose parents are at work.",
            ),
            (
                ("loot-box", "The store called it a pack. My kid called it a chance. I called the bank."),
                ("age-toggle", "I am 18, said the checkbox, in a room with a sixth grader. That is the whole child-safety stack."),
                ("default-off", "Put the store in a kid mode that is on unless a parent turns it off. Reverse the default or stop talking."),
            ),
        ),
        (
            "Search Bias",
            "Developers treat featured rows and query ranking as the real editorial page of the store.",
            (
                "If the first result is always the house app, search is not search. It is a shelf fee.",
                "Review timing that punishes independents while celebrities sail through is a thumb on the scale.",
                "A11y and privacy labels only matter if they can outrank a paid tile.",
            ),
            (
                ("house-row", "I searched for 'maps' and got the first-party tile, a paid tile, then the app people actually wanted."),
                ("review-queue", "Our update sat for 18 days. The celebrity clone shipped overnight. Editorial, apparently."),
                ("label-bury", "The privacy nutrition label is below the fold. The 'editors' choice' badge is not."),
            ),
        ),
        (
            "Small Devs",
            "Independents describe the store as a lottery: fees, review roulette, and discoverability that died when ads arrived.",
            (
                "A $99 plus 30% plus an ad auction is not a small-business program. It is a casino with a Mac Mini.",
                "When organic search dies, only people who can buy installs survive. That is a monoculture.",
                "The cute origin story in the keynote is not a policy. Look at the median revenue.",
            ),
            (
                ("ad-tax", "I used to be found. Now I buy my own users back from the store that hid them."),
                ("reject-loop", "Guideline 4.3, again, with no example. My competitor with a lawyer sailed."),
                ("median", "The keynote cited a millionaire. The median is a hobby. Say the median."),
            ),
        ),
    ),
}
