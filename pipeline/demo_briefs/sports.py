"""Sports extras beyond Sports Culture."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "League Labor": faces(
        (
            "Lockouts",
            "Players and crews treat a dark season as the only language owners still hear.",
            (
                "A lockout is a capital strike. Calling it a failure to agree is a press strategy.",
                "Staff who are not on the field eat the dark nights first. Count them in the story.",
                "If the cap is a religion, the lockout is the inquisition. Both are choices.",
            ),
            (
                ("capital-strike", "They can wait. A 24-year-old's window cannot. That is the leverage and they know it."),
                ("ushers", "The players will get a deal. I will get a winter. Put me in the lede."),
                ("cap-church", "They locked us for a number they invented. Very sacred."),
            ),
        ),
        (
            "Revenue Split",
            "The CBA as a pie chart: media money, a salary floor, and a fight over who is the product.",
            (
                "If the league is a media company, the labor is the catalog. Catalogs get a split.",
                "A floor that is a suggestion is how small markets eat the players and then ask for pity.",
                "Owners who cry poor after a team-value jump are doing stand-up.",
            ),
            (
                ("catalog", "You sold my face to a streamer. I would like a piece that looks like the piece you got."),
                ("floor-joke", "The floor had a trapdoor. The trapdoor had a spreadsheet."),
                ("team-value", "The franchise doubled. The offer did not. I can read a Forbes list."),
            ),
        ),
        (
            "Minors",
            "Farmhands describe housing, meal money, and a dream that is a wage story the big league prefers not to print.",
            (
                "A billion-dollar sport with a poverty affiliate is a choice about who may eat.",
                "If the bus is the classroom, pay like a classroom with a union, not a hostel.",
                "Raising the floor in the minors is how you stop selling a lottery as a career.",
            ),
            (
                ("meal-money", "I make a region's entertainment and cannot clear a two-bedroom. That is the farm."),
                ("bus-class", "We learn the system on I-80. I-80 does not pay overtime."),
                ("lottery", "They sold a dream. I would like a wage while I wait to see if the dream calls."),
            ),
        ),
        (
            "Media Rights",
            "Players want a cut of the stream that is the actual product — and a say in how their likeness lives forever.",
            (
                "The game is the loss leader. The clip is the store. Labor should sit at the store.",
                "A league that sells next-gen rights and then cries about competitive balance wants two religions.",
                "Likeness in a perpetual archive is a residual. Say residual.",
            ),
            (
                ("clip-store", "They monetized my dunk in 4K on a Tuesday. I got a per diem. Cute."),
                ("two-religions", "Balance in June, a mega-deal in July. Pick a god."),
                ("forever-face", "My younger self is a product. I would like a check that lasts as long as the file."),
            ),
        ),
    ),
    "College Sports": faces(
        (
            "NIL",
            "The name-image-likeness era as a labor market that still pretends to be a bake sale.",
            (
                "If a booster can buy a quarterback, the amateur is a costume.",
                "NIL that only works for a few sports is a Title IX test the brochure is not ready for.",
                "A right to your face is not a scandal. The scandal was the years without it.",
            ),
            (
                ("costume", "He has an LLC and a playbook. Call him a worker. The rest is a reunion speech."),
                ("few-sports", "The volleyball roster noticed the football collective. So will a lawyer."),
                ("years-without", "We were the product. We got a meal plan. I can do that math in public now."),
            ),
        ),
        (
            "Transfers",
            "The portal as free agency with a GPA — and a roster that is a year-to-year startup.",
            (
                "A coach can leave on a jumbotron. A player who leaves is a mercenary. That double standard had a good run.",
                "If the roster is a portal, development is a speech. Say that to the kid on the bench.",
                "Collectives that recruit in the portal are GMs. Put them on the masthead.",
            ),
            (
                ("jumbotron", "Coach got a buyout. I got a character lecture. I entered the portal."),
                ("bench-speech", "Development is for people who cannot leave. I left."),
                ("gm-booster", "The collective is the front office. The AD is a mascot."),
            ),
        ),
        (
            "Conferences",
            "Realignment as a TV map: geography is optional, the logo on the Saturday window is not.",
            (
                "A conference that spans three time zones is not a league. It is a cable package.",
                "Student-athletes who fly red-eyes for a Thursday game are the cost of the package.",
                "Rivalries that die for a bid are how you teach a region it was always content.",
            ),
            (
                ("cable-package", "We play a school I cannot drive to. The window is pretty. The biology midterm is not."),
                ("red-eye", "Thursday night, coast to coast, class on Friday. Very student."),
                ("rivalry-dead", "They sold the neighbor. We have a streaming partner now. I miss the neighbor."),
            ),
        ),
        (
            "Academics",
            "A quieter cluster still wants the degree to be a degree — clustering, eligibility, and a major that cannot travel.",
            (
                "A major that exists to keep a body eligible is not a university. It is a visa.",
                "If the travel calendar cannot coexist with a lab, the lab loses, and we should stop lying about it.",
                "Graduation rates that hide clusters are a branding exercise.",
            ),
            (
                ("visa-major", "I study eligibility. That is not in the catalog. It is in the hour."),
                ("lab-loses", "Organic chem does not care about a Thursday flight. The advisor does. Chem lost."),
                ("cluster", "We all majored in the same hallway. The rate looked fine. The hallway did not."),
            ),
        ),
    ),
    "Soccer Boom": faces(
        (
            "MLS",
            "The league as a real thing now: full buildings, a playoff that matters, and a ceiling still set by allocation money.",
            (
                "A designated player is a marketing plan. A wage structure that can keep a midfielder is a league.",
                "If the calendar still fights the world, the product will keep feeling provincial.",
                "Supporters' sections are the asset. Do not turn them into a hospitality SKU.",
            ),
            (
                ("keep-the-6", "We can sell a star. Can we keep the six? That is the boom test."),
                ("calendar", "Play in the world's season or keep being a summer league with better food."),
                ("hospitality", "The ultras built the building. The club built a cocktail. Watch which one they protect."),
            ),
        ),
        (
            "Women's Game",
            "This cluster is still facilities, travel, and a federation that discovered the team after the ratings.",
            (
                "Equal play on unequal fields is a press conference.",
                "If the men's friendly gets the stadium and the women get a college soccer park, the boom is a guest.",
                "Pay that arrived after a lawsuit is not generosity. It is a docket.",
            ),
            (
                ("college-park", "They sold out. They still got the high-school locker. Ratings are not keys."),
                ("friendly-split", "He played in a cathedral. She played in a wind tunnel. Same federation."),
                ("docket", "Do not thank them for the check. Thank the lawyers."),
            ),
        ),
        (
            "World Cup",
            "Hosts, human rights, and a month that makes casuals into theologians of the group stage.",
            (
                "A cup that washes a state is still a cup. It is also a wash. Hold both.",
                "If the infrastructure is a promise to a neighborhood that will be gone in July, count the neighborhood.",
                "Casual fandom is the point. Gatekeeping the group-stage tourist is how you stay small.",
            ),
            (
                ("wash", "I will watch. I will also read the labor report. Both are allowed in a living room."),
                ("gone-in-july", "The pitch is pretty. The block that used to be there was also pretty. One remains."),
                ("tourist", "Let people love a flag for a month. We can do tactics in club season."),
            ),
        ),
        (
            "Local Clubs",
            "The boom as a Tuesday night: amateur pitches, a second-division side, a pub that is the civic religion.",
            (
                "If MLS is the mall, the local club is the square. Starve the square and the mall is a fad.",
                "Fields that are actually lit are a parks budget, not a vibe.",
                "A supporter culture you cannot afford to enter is just another luxury box.",
            ),
            (
                ("square", "I go on Tuesday. The TV goes on Saturday. Tuesday is the boom I trust."),
                ("lit-fields", "Put lights on the county pitch. The academy can wait."),
                ("luxury-ultra", "If the scarf requires a membership I cannot pay, it is merch, not a culture."),
            ),
        ),
    ),
    "Women's Leagues": faces(
        (
            "Pay Gaps",
            "Players treat the gap as a business model, not a vibe — revenue, but also a federation that allocated the oxygen.",
            (
                "Revenue follows investment. Pretending the gap is a market is how you freeze the investment.",
                "A superstar on a second job is a league that is still a hobby in the budget.",
                "Equal commercial terms from a shared federation is the boring ask.",
            ),
            (
                ("second-job", "She trains at dawn because the night is a shift. That is not grit. That is a payroll."),
                ("freeze", "They said earn it. They also said no academy. Cute sequence."),
                ("terms", "Same sponsor, different rate. I would like the email where that was decided."),
            ),
        ),
        (
            "Facilities",
            "Locker rooms, travel, and a practice pitch that is not a shared high-school field after dark.",
            (
                "A league that cannot guarantee a working shower is not ready for a national TV story. It is ready for a lawsuit.",
                "Charter flights are not decadence when the alternative is a red-eye and a Sunday match.",
                "If the men's reserve side has the better pitch, the org chart is the story.",
            ),
            (
                ("shower", "We dressed in a hallway. The broadcast had a drone. Priorities."),
                ("red-eye", "They saved on a plane and spent it on my hamstring. Very efficient."),
                ("reserve-pitch", "The boys' B team has heat. We have a portable. I took a picture."),
            ),
        ),
        (
            "Coverage",
            "Blackouts, ticker afterthoughts, and a highlight show that still thinks there is one sport.",
            (
                "A boom you cannot find on the basic package is a boom for people with a second app.",
                "If the Sunday show gives a 40-second look, the culture will stay a 40-second look.",
                "Beat reporters are infrastructure. A tweet from the club is not a beat.",
            ),
            (
                ("second-app", "I need three logins to watch the team in my city. Piracy is a review."),
                ("40-seconds", "They had time for a horse race. They had a sliver for a championship. I saw the sliver."),
                ("beat", "Hire a person. The newsletter cannot cover a league."),
            ),
        ),
        (
            "Investment",
            "Owners, PE, and a question: is the money here to grow a league or to flip a logo?",
            (
                "Patient capital looks like academies and buses. Flip capital looks like a rebrand and a sale.",
                "If the men's club treats the women's side as a CSR unit, it will get CSR results.",
                "Public money for a stadium should include a lock on the women's tenant, in writing.",
            ),
            (
                ("rebrand-flip", "They changed the badge twice. They did not change the travel. I know a flip when I see one."),
                ("csr-side", "We are a values slide. I would like a P&L."),
                ("lock-tenant", "If the city pays the palace, write us into the palace. Not a 'best effort'."),
            ),
        ),
    ),
    "Stadium Deals": faces(
        (
            "Public Money",
            "Voters treat the billion-dollar palace as a transfer: a team that could move, a city that cannot.",
            (
                "A threat to leave is the business model. The stadium is the ransom.",
                "If the return is 'indirect', ask for the direct. Hotels will not save a school.",
                "Owner equity that is a naming-rights loop is not skin in the game. It is a hall of mirrors.",
            ),
            (
                ("ransom", "They will go to the suburbs. They always will. That is the pitch. Vote no."),
                ("indirect", "The consultant counted a hot dog twice. The millage counts once."),
                ("mirrors", "He put in 'equity' that was a loan against the city's bond. Very brave."),
            ),
        ),
        (
            "Naming Rights",
            "The building as a billboard that expires, and a civic landmark that cannot keep a name.",
            (
                "A public house with a private noun is a tell about who the house is for.",
                "If the schoolkids cannot say the name without a trademark, you sold the commons.",
                "Rights that outlast the firm leave a ghost brand on a map.",
            ),
            (
                ("private-noun", "I grew up going to a bank. It used to be a park. Progress."),
                ("kids-say", "The field trip is an ad. That should be a joke."),
                ("ghost-brand", "The sponsor died. The sign remains. We are a graveyard of logos."),
            ),
        ),
        (
            "Displacement",
            "The neighborhood under the render: eminent domain, a lost block, a 'district' that is a beer line.",
            (
                "A district that prices out the people who were the atmosphere is a mall with a mascot.",
                "Relocation inside a city can still be a removal. Count the leases.",
                "If the community benefits agreement has no teeth, it is a pamphlet.",
            ),
            (
                ("beer-line", "They called it a neighborhood. It is a queue for $12 lager."),
                ("leases", "We did not move to the suburbs. The rent moved us to a warehouse. Same city, they said."),
                ("cba-teeth", "The agreement promised jobs. It delivered a flyer. Hire a lawyer next time."),
            ),
        ),
        (
            "Parking",
            "The unglamorous fight: acres of asphalt, a surge fee, and a transit line that dies at 10pm.",
            (
                "A stadium that requires a sea of cars is a land-use bomb, not a civic jewel.",
                "Surge parking is a second ticket. Put it on the first ticket or stop the theater.",
                "If the train dies before the encore, the train is a press conference.",
            ),
            (
                ("asphalt-sea", "We paved a neighborhood so a pickup could wait. That is the deal."),
                ("surge-lot", "The lot cost more than the seat. I sat in the car and listened. Honest review."),
                ("train-10", "Last train at 10. Last out at 11. They knew. They built it anyway."),
            ),
        ),
    ),
    "Esports": faces(
        (
            "Orgs",
            "Teams as startups that miss payroll: a logo, a house, a sponsor that left in the winter.",
            (
                "A franchise that cannot make payroll is not a scene. It is a venture round with jerseys.",
                "If the org owns the players as content, the competitive part is a costume.",
                "Leagues that sell slots and then watch orgs die sold a bag, not a sport.",
            ),
            (
                ("payroll", "We practiced. The account did not. That is an org."),
                ("content-first", "They wanted clips more than a coach. We clipped. We also lost."),
                ("slot-bag", "Someone bought a chair. The chair is empty. The league still has the money."),
            ),
        ),
        (
            "Burnout",
            "A 22-year-old's career as a five-year window: bootcamps, scrims, and a sleep that never arrives.",
            (
                "A schedule that is 12 hours of the same game is an industrial injury with a webcam.",
                "Retirement at 24 is not a meme. It is a labor fact.",
                "If the only mental-health plan is a Discord mod, the org is not serious.",
            ),
            (
                ("12-hours", "I peaked in a house with no windows. That was the job description."),
                ("retire-24", "I am a veteran. I cannot rent a car. Look at that."),
                ("discord-plan", "The therapist is a channel. The channel is not licensed. I left anyway."),
            ),
        ),
        (
            "Prizing",
            "Pools that look huge on a thumbnail and small after the org's cut, the taxes, and the visa.",
            (
                "A million-dollar event that pays fifth place like a weekend is a spectacle, not a livelihood.",
                "If the org takes the prize and drips a salary, the player is a contractor in a jersey.",
                "Invitees versus qualifiers is how you freeze a class system and call it competitive integrity.",
            ),
            (
                ("fifth", "The graphic said millions. My fifth said rent. Both can be on the graphic."),
                ("drip", "They banked the trophy. I banked a stipend. I was the one on the stage."),
                ("invite", "The same ten. The qualifier is a courtesy. Say it."),
            ),
        ),
        (
            "Broadcasts",
            "Talent, delay, and a production that still treats the observer as an intern.",
            (
                "A sport that cannot show a readable fight will stay a Discord hobby on TV.",
                "Talent who actually played is not a luxury. It is how you teach a camera what matters.",
                "If the delay is a cheat tool, the broadcast is part of the ruleset. Fund it like one.",
            ),
            (
                ("readable", "Mom cannot see the fight. That is not her fault. That is your observer."),
                ("played", "Hire the person who has died on that site. The adjective streamer can wait."),
                ("delay-rules", "They saved money on the delay and lost a match to a stream sniper. Cheap."),
            ),
        ),
    ),
    "Injury Culture": faces(
        (
            "Concussion",
            "The protocol as a press conference: who saw the hit, who cleared, and a brain that does not care about the Sunday ticket.",
            (
                "A protocol that can be talked off by a star is not a protocol.",
                "If the independent neurologist is on the club's meal, independence is a lanyard.",
                "Youth leagues that copy the NFL's silence are how you inherit a generation of fog.",
            ),
            (
                ("talked-off", "He was out. He was back. The market moved. The brain did not get a memo."),
                ("lanyard", "Independent means a different logo on the same sideline. Cute."),
                ("youth-fog", "Pop Warner watched the NFL and learned the wrong lesson. I would like a different teacher."),
            ),
        ),
        (
            "Load Management",
            "Rest as a labor practice that fans still call softness — and a calendar that is the actual opponent.",
            (
                "A 82-game ad inventory is not a health plan. Sitting a star is the health plan, badly.",
                "If the league wants national TV, it can want fewer games. Both are business.",
                "Calling rest 'disrespect' is how you get a torn something in May.",
            ),
            (
                ("inventory", "They sell all 82. The tendon does not. I sit with the tendon."),
                ("fewer", "Shorten the season. Keep the ticket. I will still come. My guys might still walk."),
                ("may-tear", "He played through April for a stream. May took the rest of the year. Disrespect, they said."),
            ),
        ),
        (
            "Youth",
            "Parents describe specialization, showcases, and a 12-year-old's UCL as an industry input.",
            (
                "A calendar with no offseason is a business, not a childhood.",
                "Showcases that sell exposure are selling a lottery ticket with an ice bag.",
                "If rec dies, only the kid with a second mortgage gets a sport. That is a public-health story.",
            ),
            (
                ("no-offseason", "We played 70 games. He is 12. That is not development. That is a road trip."),
                ("ice-bag", "The showcase wanted innings. The elbow wanted a childhood. The showcase paid the coach."),
                ("rec-dead", "The park league died. The travel team has a brand. I miss the park."),
            ),
        ),
        (
            "Painkillers",
            "The quiet pharmacy: Toradol, a needle, a flight home, a later story.",
            (
                "A shot so you can sell a Sunday is labor in its raw form.",
                "If the club doctor is also the club employee, the patient is the logo.",
                "Retirees talking about the bottle are the longitudinal study we refused to run.",
            ),
            (
                ("sunday-shot", "They asked me if I could go. They meant the needle. I went."),
                ("logo-patient", "The doctor had a team mark. I had a joint. Guess who got the vote."),
                ("bottle", "We are the study. Nobody enrolled us. We enrolled ourselves in a podcast."),
            ),
        ),
    ),
    "Olympic Politics": faces(
        (
            "Host Costs",
            "Cities treat the Games as a hangover: stadiums that do not convert, a debt that does, and a bid that was a vanity.",
            (
                "A temporary sport with a permanent ruin is the usual souvenir.",
                "If the bid process is a sales department, the city is the mark.",
                "Reuse, cap, and a no-new-venues rule are the only grown-up bids left.",
            ),
            (
                ("ruin", "The velodrome is a puddle. The bond is not. That is a Game."),
                ("mark", "They sold us a mood. We bought a millage. I would like a receipt that is not a flag."),
                ("no-new", "Use the college. Use the road. If it needs a spaceship, it is a no."),
            ),
        ),
        (
            "Boycotts",
            "Athletes as diplomats they did not vote for — and a history of boycotts that punished the wrong body.",
            (
                "A boycott that sits the 22-year-old and not the federation is a morality play with a casualty.",
                "If the point is the host's law, say the law. A vibe about 'the Olympics' is how you get a press hit and a ruined cycle.",
                "Competing and speaking is also a politics. Pretending the start list is neutrality is a myth.",
            ),
            (
                ("wrong-body", "I lost my one Games. The minister did not. Remember the body."),
                ("say-the-law", "Name the statute. Then I can decide if my start is a collaboration."),
                ("start-list", "I can run and still have a mouth. The committee hates that combo."),
            ),
        ),
        (
            "Athletes",
            "The people in the village: funding, a 4-year wage, and a committee that owns the image.",
            (
                "A gold that still needs a GoFundMe is a scandal, not a human-interest piece.",
                "If Rule 40 is a muzzle on the only month they can eat, the brand is the parasite.",
                "Mental health as a press value and a cut in the stipend is a contradiction the village can see.",
            ),
            (
                ("gofundme", "She won. She still had a link in bio. That is the model."),
                ("rule-40", "They own my face in August. August is the only month the face is worth anything."),
                ("stipend-cut", "They posted a hotline and trimmed the check. I used neither."),
            ),
        ),
        (
            "Broadcast",
            "Tape delay in a live world, a rights fee that hides sports, and a prime-time that is a reality show with medals.",
            (
                "If the event is over on my phone, the tape is an insult, not a package.",
                "A rights holder that buries a sport to save a narrative is a producer, not a public square.",
                "Streaming that still needs a cable login is the hangover of the last monopoly.",
            ),
            (
                ("phone-first", "I knew the result at lunch. They packaged the surprise at 8. I am not 1998."),
                ("buried", "The final was on a channel I do not have. The talk show was on the one I do."),
                ("login", "I paid for the Games. I also paid for a bundle I do not want. Very modern."),
            ),
        ),
    ),
    "Referee Wars": faces(
        (
            "VAR",
            "The screen as a second referee: longer waits, a still that lies, and a crowd that now boos a pixel.",
            (
                "A tool that cannot admit uncertainty will freeze a bad still and call it justice.",
                "If the standard is 'clear and obvious', stop using a microscope. Microscopes are not obvious.",
                "Audio that the crowd cannot hear is a private trial in a public house.",
            ),
            (
                ("bad-still", "They picked the frame that fit the story. The next frame did not. I have eyes."),
                ("microscope", "Clear and obvious took four minutes. That is a seminar, not a match."),
                ("private-trial", "Let us hear it or stop pretending we are in the room."),
            ),
        ),
        (
            "Abuse",
            "Refs as a shortage: youth who will not sign up because a parent is a weather system.",
            (
                "A sideline that screams at a 16-year-old official is how you get no officials.",
                "If the pro game models contempt, the rec game will copy it without the paycheck.",
                "A camera on the parent is a sad solution and also the one that works.",
            ),
            (
                ("16-year-old", "She quit. He is a dentist. The dentist won. The Saturday league lost."),
                ("model", "They screamed at the VAR and then asked where the youth refs went. Geography."),
                ("camera-parent", "Film the stands. Shame is a tool. I would like a tool."),
            ),
        ),
        (
            "Pay",
            "The fee that does not match the drive, the course, and the risk of a Saturday.",
            (
                "If the match cannot clear gas and a background check, the whistle is a hobby — until it is a shortage.",
                "Pro fees that lag the media deal are a tell about who is in the product.",
                "Paying for the course and then nickel-and-diming the game is how you train people to leave.",
            ),
            (
                ("gas", "Two hours of drive, one hour of abuse, $45. I can tutor instead."),
                ("media-lag", "The window is a billion. The whistle is a stipend. I can see the window."),
                ("course", "I paid to learn. They paid me like I had not. That is the pipeline."),
            ),
        ),
        (
            "Consistency",
            "Fans want a strike zone that is a strike zone — the same one in October, the same one in April.",
            (
                "A standard that moves with a market is not officiating. It is a mood.",
                "If the league will not publish the clip with the rule, the league wants the argument more than the rule.",
                "Robo-umps will not save a culture that wants a villain. They might save a Saturday.",
            ),
            (
                ("october-zone", "It was a strike in May. It was a narrative in October. I would like a coordinate."),
                ("publish", "Show the clip and the sentence from the book. Stop the oracle act."),
                ("robo", "Give the kid a machine. Keep the human for the rest. I am tired of the morality play on ball four."),
            ),
        ),
    ),
}
