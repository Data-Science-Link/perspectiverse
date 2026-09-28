"""Media extras beyond Media Trust."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Newsroom Cuts": faces(
        (
            "Buyouts",
            "Reporters treat the buyout as the newsroom's last craft: lose the memory on purpose, keep the brand.",
            (
                "A buyout that targets the people who remember the last scandal is how you guarantee the next one.",
                "If the chain can afford a dividend, the buyout is a preference, not a weather event.",
                "Institutional knowledge does not live in the CMS. It lives in the person you just paid to leave.",
            ),
            (
                ("memory", "They bought out the person who knew where the bodies were. The bodies will wait."),
                ("dividend", "The letter said sustainability. The 10-K said a payout. I can read both."),
                ("cms", "The style guide is not a senior. The senior is a senior. Stop confusing them."),
            ),
        ),
        (
            "Beats",
            "The empty chair: courts, schools, and a city hall that now live-streams to nobody who can file.",
            (
                "A town without a courts reporter has a prosecutor with a camera and no second camera.",
                "Beats are how you catch a pattern. General assignment is how you catch a press release.",
                "If the school board is uncovered, the school board is unsupervised. That is the beat.",
            ),
            (
                ("second-camera", "They live-stream. Nobody files. The live-stream is not a newspaper."),
                ("pattern", "I used to know which landlord owned the complaints. Now we have a vibe and a TikTok."),
                ("unsupervised", "The board stopped waiting for me. I do not work there. That was the point of me."),
            ),
        ),
        (
            "Private Equity",
            "This cluster names the owner: a fund that wanted the real estate, the skeleton staff, and the remaining ad stub.",
            (
                "A newsroom that is a real-estate play will always find the news expendable. The news is not the asset.",
                "Hollowing a metro and keeping the masthead is a fraud on the subscriber.",
                "If the cap table cannot survive a public-benefit structure, it should not own a public square.",
            ),
            (
                ("the-building", "They sold the building and rented us the fluorescent. The journalism was the remainder."),
                ("masthead", "The logo is healthy. The hallway is a ghost. Subscribers bought the hallway."),
                ("cap-table", "A fund with a five-year clock cannot own a beat that takes seven years to learn."),
            ),
        ),
        (
            "Nonprofits",
            "A hopeful path: civic sites, a membership, a board that is not a hedge — and a grant that can still steer.",
            (
                "Nonprofit is a tax status, not a virtue. Read the donors.",
                "Membership that replaces display ads can work if the journalism is local enough to feel like a utility.",
                "A grant for 'innovation' that skips payroll is how you get a newsletter and a burnout.",
            ),
            (
                ("read-donors", "Our board is cleaner than the chain. It is still a board. I print the 990."),
                ("utility", "People pay for the zoning. They will not pay for a vibe. Good. File the zoning."),
                ("innovation-skip", "They funded a vertical video. I needed a courts person. The video is pretty."),
            ),
        ),
    ),
    "Streaming Wars": faces(
        (
            "Bundles",
            "The new cable: four apps that add up to the bill you left, plus a password theater.",
            (
                "Unbundling that rebundles at the same number is a choreography, not a discount.",
                "If the live sports are the reason, sell the sports without the sitcom graveyard.",
                "A bundle that still needs four logins is not a bundle. It is a folder.",
            ),
            (
                ("same-number", "I left $140. I am at $130 and a headache. Very disruptive."),
                ("just-sports", "I do not want the baking show. I want Saturday. Sell Saturday."),
                ("folder", "Four passwords, one 'bundle'. I have a drawer that works the same way."),
            ),
        ),
        (
            "Sports Rights",
            "The war is the game: every league as a hostage that moves the subscriber number.",
            (
                "A sport that lives on a rotating app is not a community. It is a leaky pipe.",
                "If the rights fee cannot be paid by ads, it will be paid by a tax on people who wanted one team.",
                "Blackouts in a streaming world are a special kind of contempt.",
            ),
            (
                ("leaky-pipe", "The team moved again. My app did not. I pirated a feeling of being a citizen."),
                ("one-team-tax", "I wanted the local. I bought a continent. That is the fee."),
                ("blackout-stream", "They blacked out a stream I already pay for. That is art."),
            ),
        ),
        (
            "Churn",
            "Subscribe for a season, leave, come back — the business model that trains you not to be loyal.",
            (
                "A library that is a rental will be rented. Stop gasping at the churn number.",
                "If the show is the hook, the hook leaving is why I leave. That is not mystery churn.",
                "Win-back offers that undercut the loyal price punish the person who stayed.",
            ),
            (
                ("rental", "I stack for awards season and dump in February. They taught me that."),
                ("hook-left", "You canceled the show. I canceled you. Cause and effect."),
                ("win-back", "The new customer got $3. I got a thank-you. I became a new customer."),
            ),
        ),
        (
            "Originals",
            "Volume as a strategy: 40 titles so two can trend, and a mid-budget that cannot breathe.",
            (
                "A slate that is a firehose is how you get no memory of any title.",
                "If the algorithm orders the show, the show will look like the algorithm.",
                "Killing a season-two to juice a metric is how you teach artists to work elsewhere.",
            ),
            (
                ("firehose", "I cannot remember what they made. That was the plan, I think."),
                ("looks-like-algo", "Every show is a dark city and a sad cop. The thumbnail is the writer."),
                ("season-two", "They asked for loyalty and then ran a write-off. I can also write off an app."),
            ),
        ),
    ),
    "Deepfakes": faces(
        (
            "Elections",
            "A clip of a candidate who did not say it — and a 48-hour lag that is the whole election in a county.",
            (
                "Speed is the weapon. A correction that arrives after early vote is a diary.",
                "If platforms wait for a government flag, the flag will be late on purpose somewhere.",
                "Provenance that normal people can see — a watermark a grandma trusts — is the boring product we do not have.",
            ),
            (
                ("48-hours", "The clip hit Tuesday. The denial hit Thursday. Wednesday was Election Day here."),
                ("flag-late", "They wanted an official. The official wanted a letter. The letter wanted a week."),
                ("grandma-mark", "If she cannot tell, the feature failed. Do not tell me about a C2PA PDF."),
            ),
        ),
        (
            "Porn",
            "Nonconsensual faces as the actual mass use — not the election seminar, the revenge file.",
            (
                "A law that only talks about politicians will miss the teenager in the file.",
                "Platforms that host the catalog and shrug at the takedown are the business model.",
                "Consent is the whole product. A deepfake sex file without it is an assault with extra steps.",
            ),
            (
                ("not-the-seminar", "Stop starting with the president. Start with the girl in my class."),
                ("takedown-shrug", "I filed. They asked for a court. The file had a head start."),
                ("assault", "Call it what it is. The model is a weapon the moment it has her face."),
            ),
        ),
        (
            "Watermarks",
            "Engineers treat invisible marks as a maybe: stripped by a screenshot, ignored by a feed.",
            (
                "A watermark that dies at the screenshot is a classroom demo, not an election tool.",
                "If the detector is a paid API, the lie will be free and the truth will be a vendor.",
                "Credentials help journalists. They do not help an uncle. Design for the uncle.",
            ),
            (
                ("screenshot", "I filmed the TV with a phone. Your invisible soup left."),
                ("paid-truth", "The detector costs. The fake does not. That market will not self-correct."),
                ("uncle", "Put a fat, ugly, durable mark on official video or stop talking about uncles."),
            ),
        ),
        (
            "Law",
            "Statutes trying to catch a file: disclosure, criminalization, and a First Amendment fight that is not hypothetical.",
            (
                "A disclosure that a faker will not attach is a rule for the already-honest.",
                "Criminal law that hits the maker and ignores the platform will miss the machine.",
                "Parody is real. So is a factory of her face. A statute that cannot tell them apart will be used badly and also used.",
            ),
            (
                ("already-honest", "I labeled my satire. The factory did not. The law found me. Cute."),
                ("the-machine", "Sue the kid. Keep the site. That is a preference, not a remedy."),
                ("tell-apart", "Write a test that a human can run. If you cannot, you wrote a vibe."),
            ),
        ),
    ),
    "Podcast Politics": faces(
        (
            "Hosts",
            "The three-hour ramble as a primary: parasocial trust that outruns a party and a newspaper.",
            (
                "A host who never has to face a rival in the room is a church, not a debate.",
                "If the audience is larger than the nightly news, the host is a party officer. Act like it.",
                "Accountability that is a superchat is not accountability. It is a tip jar.",
            ),
            (
                ("church", "He talked for three hours. Nobody who disagrees got a mic. That is a liturgy."),
                ("party-officer", "He moved a county. The county party sent a fruit basket. I would like a debate."),
                ("superchat", "I paid $5 to ask a real question. He read a funnier one. Market, I guess."),
            ),
        ),
        (
            "Ads",
            "Supplements, gold, and a read that sounds like a friend — because that is the product.",
            (
                "A political show that is funded by a powder is an independent media with a cart.",
                "If the host will not disclose the cut, the cut is the politics.",
                "Host-read ads that skip the risk are why people trust the show more than a network — and that is the hazard.",
            ),
            (
                ("powder-pol", "He explained the election and then a hormone. I would like those separated."),
                ("the-cut", "Say the number. Friendship that invoices me is a job."),
                ("skip-risk", "The network has a legal. The garage has a vibe. The vibe sells the gold."),
            ),
        ),
        (
            "Parties",
            "Campaigns treat the long show as the new Iowa: sit for three hours or do not get the men who do not watch TV.",
            (
                "A primary that happens in a studio apartment is still a primary. The rules did not arrive.",
                "If only one faction will sit for the ramble, the ramble is a gate, not a conversation.",
                "Parties that cannot produce a guest who can go three hours will lose that room. That may be fine. Know it.",
            ),
            (
                ("new-iowa", "He did not do the dinner. He did the garage. The dinner is a museum."),
                ("gate", "If you will not go on, you do not get those votes. That is a rule even if you hate the host."),
                ("three-hours", "Our candidate is a memo person. The room is a story person. We lost the room."),
            ),
        ),
        (
            "Clips",
            "The 40-second outrage as the actual show — a cut that the host always says is out of context.",
            (
                "A clip economy will pull the worst 40 seconds. Design the hour knowing that, or stop gasping.",
                "If the clip is the fundraising, the hour is a farm system for the clip.",
                "Context that lives behind a three-hour wall is not context. It is a moat.",
            ),
            (
                ("gasp", "He said the quiet part because the quiet part clips. I am not a detective."),
                ("farm-system", "The show exists to feed a timeline. The timeline is the boss."),
                ("moat", "Put the correction in a 20-second clip or admit you like the moat."),
            ),
        ),
    ),
    "Comment Sections": faces(
        (
            "Moderation",
            "Mods as unpaid legislatures: brigades, slurs, and a toolset from 2008.",
            (
                "A board without a person with a banhammer is a storm drain.",
                "If the business model needs the fight, the mod is a janitor in a casino.",
                "Appeals that are a void teach good users to leave. That is how a section dies into its worst 5%.",
            ),
            (
                ("storm-drain", "We asked for a human. They gave us a filter. The filter loves a slur it has not met."),
                ("janitor", "I volunteer so a company can sell the argument. I stopped."),
                ("worst-5", "The decent people left. The metrics did not notice. The metrics are the worst 5%."),
            ),
        ),
        (
            "Anonymity",
            "Real-name as a cure versus a shield for the person who will get doxxed for a local take.",
            (
                "Anonymity is how a nurse criticizes a hospital. It is also how a nobody becomes a mob.",
                "A real-name rule that the famous ignore is a rule for the weak.",
                "If the threat model is the boss and the spouse, real name is a gate, not a virtue.",
            ),
            (
                ("nurse", "I can tell you about the ratio if you do not tell my unit. That is the whole feature."),
                ("famous-ignore", "He has a brand. I have a lease. The policy found the lease."),
                ("spouse", "My take is local. My last name is a weapon. I will keep the handle."),
            ),
        ),
        (
            "Rage Bait",
            "The headline that exists to farm the first comment — a business model, not a misfire.",
            (
                "If the most-shared piece is the one that makes a stranger into a type, the desk is in on it.",
                "A comment that is the product will be produced. Hire accordingly or cut the section.",
                "Pre-bunking in the piece is slower. It also does not print as well. That is the fork.",
            ),
            (
                ("type", "They turned a neighbor into a demographic. The comments did the rest. By design."),
                ("product", "The piece was a match. I am not lighting it anymore."),
                ("fork", "I want the slower piece. Their KPI does not. I left a note. Then I left."),
            ),
        ),
        (
            "Local",
            "The last useful comments: a school-board thread, a snow-plow argument, a name who actually lives there.",
            (
                "Nationalizing a local thread is how you get a civil war in a pothole post.",
                "A login from 2,000 miles away should not out-vote a block. Geo is a feature.",
                "If the paper kills comments instead of staffing them, it kills the last public meeting some people had.",
            ),
            (
                ("pothole-war", "It was about a stop sign. Then it was about the president. Then it was unusable."),
                ("geo", "Ban the zip codes that do not pay the millage. Radical. Also obvious."),
                ("last-meeting", "The comments were messy and local. The Facebook group is worse. You had something."),
            ),
        ),
    ),
    "Public Broadcasting": faces(
        (
            "Funding",
            "The pledge week, the appropriation, and a threat that is now a season.",
            (
                "A public that will not pay a per-capita coffee for a newsroom will get a newsroom that sounds like a donor.",
                "If the federal line is a hostage every year, the programming will learn to be small.",
                "Membership is real. It is also older. A next generation that never pledged is a clock.",
            ),
            (
                ("coffee", "I can do $8 a month. I cannot do a culture war about $0.50 of federal. Both are the budget."),
                ("hostage", "They taught the show to whisper. Whispering is not a public service. It is a survival skill."),
                ("clock", "The members are 67. The app is 22. Someone has to introduce them."),
            ),
        ),
        (
            "Bias Fights",
            "The perennial audit: is it a commons or a faction with a tote bag.",
            (
                "A newsroom that will not cover its own side's mess is a faction. Run the test in public.",
                "If the complaint is always the same three stories, it is a brand war, not an edit.",
                "Ombuds that have a staff and a slot are the adult version. Twitter notes are not.",
            ),
            (
                ("own-side", "When they bury our mess I leave. When they bury yours I also leave. That is the test."),
                ("three-stories", "It is always the same clip. I want an edit, not a relic."),
                ("ombuds", "Give me a critic on payroll. Not a host who says we take this seriously."),
            ),
        ),
        (
            "Rural",
            "Transmitters, weather, and a station that is the last reporter in a county.",
            (
                "When the commercial tower goes quiet, the public one is the weather. Remember that in the hearing.",
                "A rural newsroom of one is still a newsroom. A livestream of the mill is not a replacement.",
                "If the map of members is coastal, the rural service is a charity. Fund it like a utility.",
            ),
            (
                ("weather", "The warning came from them. The rest is a culture war. I like not dying."),
                ("mill-stream", "The mill does not investigate the mill. That is why we had a person."),
                ("utility", "Do not make me pledge for a transmitter. Make it a line item like the road."),
            ),
        ),
        (
            "Kids",
            "The remaining commons for children: no ads for sugar, a show that is actually for them.",
            (
                "A public kids' block is industrial policy for attention. The commercial one is a store.",
                "If it disappears into a gated app, it is not public. It is a perk.",
                "Defending the kids' service is easier than defending the prime-time. Start there if you need a coalition.",
            ),
            (
                ("store", "I can tell who paid for the cartoon. The public one still feels like a library."),
                ("gated", "If I need a member login for the four-year-old, you lost the plot."),
                ("coalition", "Fight about the host later. Keep the street on the screen. That one I can whip votes for."),
            ),
        ),
    ),
    "Book Culture": faces(
        (
            "Bans",
            "The list, the board, the librarian: a fight that is about power more than a single title.",
            (
                "A process that hides a book from a 17-year-old is not parenting. It is a public-square decision.",
                "If the list is a national template, the local board is a franchise.",
                "Staffing the librarian is the anti-ban. Empty rooms get lists.",
            ),
            (
                ("17", "She can drive. She cannot take the book. That is a theory of adulthood I do not share."),
                ("template", "The list did not come from this county. The county still did the work."),
                ("empty-room", "They cut the clerk and then found a book to fight. Sequencing is the tell."),
            ),
        ),
        (
            "Indie Shops",
            "The remaining physical discovery: a buyer with a taste, a reading, a town that still has a third place.",
            (
                "A shop that can survive rent is a cultural policy. Amazon is not a shop.",
                "If the only copies are a website, the accident of browsing dies. Accidents are how midlist lives.",
                "Readings that pay the author in wine are still a ladder. Lose them and you have a platform and a void.",
            ),
            (
                ("rent", "Our landlord discovered 'vibrancy'. The rent discovered a number. We have six months."),
                ("midlist", "Nobody browses a warehouse. That is why the table in front matters."),
                ("wine-ladder", "I met my readers next to a folding chair. The algorithm has not replicated the chair."),
            ),
        ),
        (
            "BookTok",
            "A discovery engine that can make a novel and also flatten a shelf into tropes.",
            (
                "A 15-second cry can sell 200,000 copies. It can also make every cover a sad girl in a meadow.",
                "If the buyer is a trope tag, the writer will write the tag. That is not mysterious.",
                "Shops that ignore the app will miss a generation. Shops that become the app will miss a spine.",
            ),
            (
                ("meadow", "I like a cry. I also like a sentence. The cry is winning the jacket."),
                ("the-tag", "They asked if it was enemies-to-lovers. It is a war novel. We lost the war novel."),
                ("spine", "Put the phone down and face out the weird one. That is still a job."),
            ),
        ),
        (
            "Advances",
            "The bet that shrank: midlist checks that cannot float a year, and a debut that has to be a supernova.",
            (
                "An advance that is a round of drinks is not a profession. It is a hobby with a publicist.",
                "If only the already-platformed get the living, the living is an influencer job.",
                "Earn-out math that hides in a statement every six months is how you keep writers guessing instead of writing.",
            ),
            (
                ("drinks", "The check was a month of rent in 2012. It is a dinner now. I still have a craft."),
                ("platformed", "They asked for my followers before the pages. The pages were the job."),
                ("six-months", "I cannot see the number. The number is my wage. That is a factory with a fog machine."),
            ),
        ),
    ),
    "Celebrity News": faces(
        (
            "Paparazzi",
            "The old hunt with new drones: a child, a sidewalk, a market that still pays for the scare.",
            (
                "A photo of a kid is not news. It is a bounty.",
                "If the outlet will not run it, the Discord still might. The market moved. The harm did not.",
                "Distance laws that a drone laughs at are how you know the statute is from a different century.",
            ),
            (
                ("bounty", "They waited at the school. That is not journalism. That is a trap with a lens."),
                ("discord", "The mag passed. The board did not. The kid is still in the file."),
                ("drone", "The sidewalk law is cute. The air is a product now."),
            ),
        ),
        (
            "PR",
            "Access as the currency: a junket, an embargo, a story that is a trade.",
            (
                "A desk that cannot bite the hand that seats it is not a desk. It is a brochure.",
                "Embargoes are logistics. Embargoes that are punishments are a leash.",
                "If the only quotes are approved, say advertorial. The reader can do the rest.",
            ),
            (
                ("brochure", "We got the sit-down and lost the sentence. I would like the sentence."),
                ("leash", "They pulled the next one because we ran a photo. That is a boss, not a source."),
                ("advertorial", "Label it. I can enjoy a junket that tells me it is a junket."),
            ),
        ),
        (
            "Stans",
            "Fandom as a newsroom: speed, loyalty, and a ratio that can scare a reporter off a fact.",
            (
                "A stan army is an unaccountable editor. They will edit you in public.",
                "If the fact is true, the ratio is not a rebuttal. It is weather.",
                "Access that depends on not angering a fandom is how you get fanfic in the paper.",
            ),
            (
                ("unaccountable", "They ratioed a filing. The filing is still a filing. I kept it in the piece."),
                ("weather", "I do not cover the weather as a vote. I should not cover a ratio as a correction."),
                ("fanfic-paper", "We ran the narrative they wanted. We called it reporting. It was a truce."),
            ),
        ),
        (
            "Privacy",
            "The line: a public figure's work versus a medical file, a kid, a door.",
            (
                "Public interest is not public appetite. The second one pays. The first one is the job.",
                "A door is a door. Crossing it is a choice you cannot walk back with a 'we regret'.",
                "Health and children are the easy tests. Failing them is how you earn the blockade.",
            ),
            (
                ("appetite", "They wanted the divorce. We had the labor story. We ran the divorce. I quit a little."),
                ("the-door", "Once you are in the kitchen you are not a reporter. You are a thief with a notepad."),
                ("easy-tests", "Leave the kid. Leave the chart. The rest we can fight about like adults."),
            ),
        ),
    ),
    "Documentary Boom": faces(
        (
            "True Crime",
            "A genre that can be a public record and a second victimization — often in the same three episodes.",
            (
                "If the family did not ask for a prestige telling, the prestige is for us, not for them.",
                "A boom that needs a body every Friday will invent a style and call it justice.",
                "Court records are public. Reenactments are a choice. Label the choice.",
            ),
            (
                ("for-us", "They did not consent to be a season. We consented to a subscription. That math is the ethics."),
                ("every-friday", "The feed wants a victim. The victim wanted a Tuesday. We have a feed."),
                ("reenact", "Put 'dramatization' on the scare. I can still watch. I would like to know I am watching a skit."),
            ),
        ),
        (
            "Access",
            "The deal: embed, archive, a subject who can shut the cut.",
            (
                "A film that cannot bite its access is an authorized biography with better light.",
                "If the subject has kill rights, say so in the first card. The audience is not a child.",
                "Archives that only the well-funded can license are how history becomes a luxury.",
            ),
            (
                ("authorized", "We had the living room. We lost the knife. The living room looked great."),
                ("kill-rights", "Tell me in minute one. I will calibrate. Do not surprise me in the trades."),
                ("luxury-history", "The footage exists. The fee is a gate. Public broadcasters used to blow that gate up."),
            ),
        ),
        (
            "Streaming",
            "A slot on the home screen as the new festival — and a two-week window that is the whole life.",
            (
                "A doc that is a thumbnail war will be cut like a thumbnail war.",
                "If the streamer owns the life rights forever, the filmmaker is a vendor.",
                "Festivals that cannot lead to a life outside an algorithm are a party with a tote.",
            ),
            (
                ("thumbnail", "They asked for a face in pain at 1:1. That is not a cut. That is a store."),
                ("vendor", "I made it. They have it until the heat death. I have a rate."),
                ("tote", "We won a prize and a weekend. The weekend ended. The topic did not."),
            ),
        ),
        (
            "Ethics",
            "Informed consent as a process, not a release form; duty of care after the premiere.",
            (
                "A release signed in a crisis is not informed. It is a document.",
                "Duty of care that ends at the credit roll is how you dump a person into a comment section.",
                "If the film can get someone harmed, the harm is part of the runtime. Budget for it.",
            ),
            (
                ("crisis-form", "She signed on a bad day. We had a lawyer. That is not a fair fight."),
                ("comment-dump", "The premiere was a party. The replies were a weather system. We left her in it."),
                ("budget-harm", "Hire the aftercare. If you cannot, you cannot afford the story."),
            ),
        ),
    ),
}
