"""Entertainment extras."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Franchise Fatigue": faces(
        (
            "Sequel Glut",
            "Viewers treat the calendar as a photocopy machine: another number in the title, another weekend of déjà vu.",
            (
                "A sequel that exists to keep a slot warm is not a story. It is a timeshare.",
                "When every original is a pilot for a universe, nobody is serving the two hours you paid for.",
                "Fatigue is a market signal. Studios keep reading it as a branding problem.",
            ),
            (
                ("part-seven", "I do not hate the characters. I hate that they will never be allowed to end."),
                ("slot-warm", "The date was booked before the script. You can feel it in act two."),
                ("universe-tax", "I bought a ticket to a movie and got homework for a slide deck."),
            ),
        ),
        (
            "Ticket Prices",
            "Families describe a night out as a luxury SKU: dynamic seating, $9 water, and a film that will be home in 45 days.",
            (
                "If the window is six weeks, the premium has to be the room, not the file.",
                "Dynamic pricing at a multiplex is how you train people to wait for the couch.",
                "A kid's birthday at the movies should not require a payment plan.",
            ),
            (
                ("9-water", "The movie was fine. The concession was a second mortgage. I paused the habit."),
                ("45-days", "Why is opening weekend a tax if the file is already on the truck to my TV."),
                ("birthday", "Four kids, one PG, one regret. We do the backyard now."),
            ),
        ),
        (
            "Originals",
            "A stubborn cluster still wants a new world, a new face, and a studio that can live with a single movie.",
            (
                "Originals need a budget that is not an apology and a weekend that is not a punishment.",
                "Mid-budget adult films did not die of taste. They died of a spreadsheet that only speaks franchise.",
                "If the algorithm only greenlights awareness, awareness is all you will get.",
            ),
            (
                ("mid-budget", "Give me $40 million and a novelist. Keep the cameo from 2012."),
                ("punish-weekend", "They dumped the original in October against a sequel and called it data."),
                ("new-face", "I do not need a universe. I need a person I have not met and two hours."),
            ),
        ),
        (
            "IP Law",
            "This view is the mouse and the estate: copyright terms that keep a century of work in a vault.",
            (
                "A term that outlives the grandchildren is not an incentive for the artist. It is a portfolio for the firm.",
                "Fan works that get a takedown while the studio sleeps on a sequel is a weird allocation of vigor.",
                "Public domain is how culture compounds. Forever-minus-a-day is how it calcifies.",
            ),
            (
                ("vault", "The estate is 'exploring options'. The options are a candle and a lawsuit."),
                ("fan-edit", "I made a trailer. They made a lawyer. The sequel is still vapor."),
                ("compound", "Let the mouse go. We have new stories if you stop sitting on the old ones."),
            ),
        ),
    ),
    "Concert Economy": faces(
        (
            "Dynamic Tickets",
            "Fans treat the map as an auction: the price that moves while you hover is the show.",
            (
                "A face-value that is a rumor is not a ticket. It is a hunt.",
                "If demand is real, print more dates. Do not invent a surge that punishes the person who was online on time.",
                "Platinum rows that were just rows last tour are a transfer from regulars to a yield manager.",
            ),
            (
                ("hover", "The number changed while I typed my zip. That is not scarcity. That is software."),
                ("more-dates", "They can add a night. They added a price instead."),
                ("platinum", "I used to sit there. Now a bot sits there. Same concrete."),
            ),
        ),
        (
            "Fees",
            "The service charge as a second price — larger than the artist in some screenshots, never in the headline number.",
            (
                "A fee that appears after the button is a bait price. Retail already has a word for that.",
                "If the venue and the platform are the same firm, the 'third-party fee' is a skit.",
                "All-in pricing is the minimum adult behavior. The rest is a dark pattern with a band.",
            ),
            (
                ("after-click", "The ticket was $49 until it was $91. I did not buy a different night."),
                ("same-firm", "They charged me to use themselves. Very innovative."),
                ("all-in", "Show the number. I can do arithmetic. I refuse to do a scavenger hunt."),
            ),
        ),
        (
            "Openers",
            "Support acts describe a tour economy that wants a full set for gas money and a merch table in a hallway.",
            (
                "A 30-minute set that costs a week of travel is an internship with a kick drum.",
                "If the headliner cannot float the opener's bus, the ecosystem is a pyramid with a laser show.",
                "Playlists do not replace a room that pays. Rooms that pay are a policy of the headliner and the promoter.",
            ),
            (
                ("gas-money", "I opened for 2,000 people and cleared parking. The parking was not metaphorical."),
                ("bus", "They have a convoy. We have a van and a hope. That used to be a ladder. It is a cliff."),
                ("playlist", "Spotify did not buy the gas. A guarantee would."),
            ),
        ),
        (
            "Venue Monopolies",
            "This cluster names the amphitheater chain: one firm, one beer, one photo policy, one radius clause that kills the club date.",
            (
                "A radius clause that blanks a city is how you get one night and a desert.",
                "If the club cannot book the baby band because the shed owns the name, the pipeline is a mall.",
                "Vertical tickets, beer, and media is not a night out. It is a company town with a lawn.",
            ),
            (
                ("radius", "They played the shed. The club two miles away is dark for a month. That is the clause."),
                ("baby-band", "The development room died. The algorithm is not a room."),
                ("one-beer", "I miss a bartender who is not a vendor code. That is the monopoly on my tongue."),
            ),
        ),
    ),
    "Creator Burnout": faces(
        (
            "Algorithm Churn",
            "Creators describe ranking as a boss that rewrites the job every Tuesday.",
            (
                "If the format that paid last month is punished this month, you do not have a craft. You have a weather report.",
                "A feed that demands daily output is a time clock. Call it a time clock.",
                "Diversifying off-platform is the only union a ranking system cannot break — and it is exhausting, which is the point.",
            ),
            (
                ("tuesday", "Shorts died. Lives lived. I am a different species every quarter."),
                ("daily", "The mortgage wants a streak. My neck wants a day. Guess which one I sold."),
                ("off-platform", "I am building a list so a teenager at a company cannot zero me. That is the whole business now."),
            ),
        ),
        (
            "Brand Deals",
            "The ad read as wage: 34 edits from a brand manager who does not watch the channel.",
            (
                "A deal that takes 20 hours of revisions is a production job with influencer branding.",
                "When the only living wage is a supplement pitch, the audience is right to flinch.",
                "Whitelisting that lets the brand run your face forever is a residual you did not keep.",
            ),
            (
                ("34-edits", "They wanted authentic. They also wanted a legal department's idea of a joke. Authentic lost."),
                ("supplement", "I will not sell a powder to pay rent. That limits my career to people with a trust or a spouse."),
                ("whitelist", "They ran my face for a year. I ran out of the check in a week."),
            ),
        ),
        (
            "Mental Health",
            "A darker thread: comments as a workplace hazard, and a metric that sits on the nervous system.",
            (
                "A job whose performance review is thousands of strangers is not 'just posting'.",
                "Kids in the comments of an adult's workplace is a design failure.",
                "Taking a week off and returning to a dead account is why people do not take a week off.",
            ),
            (
                ("review", "My boss is a comment section. OSHA has not caught up."),
                ("kids-in-replies", "A 13-year-old told me to die under a video about soup. That is the factory floor."),
                ("week-off", "Rest is a career risk. That sentence is the product."),
            ),
        ),
        (
            "Unions",
            "A smaller group wants a contract: residuals, a floor, and someone who can call the platform a boss.",
            (
                "If the company can zero your wage without a call, you are labor. Act like it.",
                "A union that only covers traditional sets will miss the people who are the new set.",
                "Collective bargaining over ranking is hard. Collective bargaining over pay floors and takedowns is not mystical.",
            ),
            (
                ("zeroed", "They demonetized me into a part-time job. I would like a steward."),
                ("new-set", "I am the studio, the on-air, and the intern. Traditional coverage skips all three."),
                ("floor", "A minimum for a view that they already sold. Radical, I know."),
            ),
        ),
    ),
    "Gaming Culture": faces(
        (
            "Crunch",
            "Studio workers still describe the last six months as the actual production schedule — unpaid overtime as a genre convention.",
            (
                "A ship date that requires 80-hour weeks was a lying ship date.",
                "Crunch that is 'voluntary' in a room that knows who gets the next title is not voluntary.",
                "Live-service that never leaves crunch is a business model, not a bad project.",
            ),
            (
                ("80-hours", "The trailer looked great. The people who made it looked like a warning label."),
                ("voluntary", "I volunteered the way you volunteer in a burning room."),
                ("forever-crunch", "We shipped and then we shipped the battle pass. The couch is a rumor."),
            ),
        ),
        (
            "Live Service",
            "Players treat the $70 box as a brochure for a mall that will nickel them until the servers go dark.",
            (
                "A game that is a store with a tutorial is honest. A story that is a store is a bait.",
                "When the campaign is an ad for a season pass, the critics are not being precious. They are reading the SKU.",
                "Sunsetting a title you sold as a world is a landlord move.",
            ),
            (
                ("mall", "I wanted a campaign. I got a carousel. The carousel wanted my card."),
                ("season", "The ending is in the shop. That used to be a joke."),
                ("sunset", "They turned off a place I paid to live in. Landlords at least leave you the furniture."),
            ),
        ),
        (
            "Mods",
            "This cluster still believes user-made work is the soul — and notices platforms squeezing it into a storefront.",
            (
                "A workshop that pays the platform first is not a commons. It is a mall with a hammer icon.",
                "Single-player mods that get a ToS scare because of a live-service future are a tell.",
                "If the official tools are worse than the community's, hire the community or get out of the way.",
            ),
            (
                ("workshop-cut", "She made the city. They made the 30%. Cute partnership."),
                ("tos-scare", "My single-player house is a policy risk now. The policy is the cash shop."),
                ("hire-them", "The best lighting in the game is a free mod. That should embarrass a director."),
            ),
        ),
        (
            "Toxicity",
            "Voice chat, ranked, and a pipeline that teaches kids a slur before a skill — moderation as an afterthought.",
            (
                "A ranked mode that rewards tilt is not a community. It is an unmoderated workplace for children.",
                "Reporting that goes to a void trains people to mute and leave. That is a churn machine.",
                "If the money is in engagement, cruelty will keep winning until it is expensive.",
            ),
            (
                ("ranked-kid", "He learned the slur in unrated. The tutorial was other people."),
                ("report-void", "I reported a hate raid. The reply was a skin. Very serious."),
                ("expensive", "Fine the clan, drop the LP, slow the queue. Make it cost. Kindness will not volunteer."),
            ),
        ),
    ),
    "Streaming Queue": faces(
        (
            "Password Rules",
            "Households treat the crackdown as a raise: the shared account was the product, then it was a crime.",
            (
                "A price that assumed four houses was the price. Changing the assumption is a hike.",
                "If the interface still begs me to share until it bills me for sharing, the copywriters should meet the lawyers.",
                "People will pirate a feeling of being punished. That is not a moral tale. It is UX.",
            ),
            (
                ("four-houses", "Mom had the login. That was the plan in 2019. The plan got a fee."),
                ("beg-then-bill", "The app said share. Then it said extra member. I said torrent, hypothetically."),
                ("punished", "I will pay a fair number. I will not pay a gotcha. The gotcha is the strategy."),
            ),
        ),
        (
            "Show Cancellations",
            "Fans describe three-season graves: tax write-offs, vanishing finales, and a library that is a trapdoor.",
            (
                "A show that cannot close a story is a product that used the audience as a test balloon.",
                "Removing a title you already sold in a bundle is a special kind of bait.",
                "If the incentive is a write-off, do not ask for loyalty. Ask an accountant.",
            ),
            (
                ("season-3", "They asked me to care and then deleted the ending. I can also delete the app."),
                ("trapdoor", "It was in my list on Tuesday. Wednesday it was a tax event."),
                ("loyalty", "Stop the 'thank you for being on this journey' email. The journey was a spreadsheet."),
            ),
        ),
        (
            "Discovery",
            "The home screen as a junk drawer: 40 thumbnails, none of them the thing you heard about.",
            (
                "A catalog you cannot search is a warehouse with a slot machine at the door.",
                "If the row is paid placement, say ad. 'Top 10' that is a deal is a lie.",
                "Recommendation that only knows what you finished will never know what you would have loved.",
            ),
            (
                ("junk-drawer", "I scrolled for 25 minutes and watched nothing. That is not choice. That is fog."),
                ("top-10-ad", "Number three paid to be number three. I would like a receipt."),
                ("finished", "It keeps serving me the last thing. I finished it. That is the point of finishing."),
            ),
        ),
        (
            "Ads",
            "The cheaper tier that still pauses you — and a premium that quietly grew ads anyway.",
            (
                "A subscription with commercials is cable with a worse remote.",
                "If the ad load grows after the bait price, the price was a lie.",
                "Skipping that is not skipping is a contempt for the person who already paid.",
            ),
            (
                ("cable-again", "I left Comcast for this. This is Comcast with a poster of a lady in space."),
                ("bait-load", "Five ads became eight. The bill stayed. I did not."),
                ("paid-anyway", "I am on the expensive plan. I still got a car. Explain it without 'engagement'."),
            ),
        ),
    ),
    "Awards Season": faces(
        (
            "Campaigns",
            "For-your-consideration as a second industry: parties, screeners, and a budget that looks like a campaign, because it is.",
            (
                "A statue that can be bought with a party circuit is a trade-show prize.",
                "If voters do not see the small film, the small film did not lose. It was not in the room.",
                "Publicists are the electorate's weather. Pretending otherwise is how we get the same five names.",
            ),
            (
                ("party-circuit", "The movie was good. The canapés were the campaign. I can tell which one they funded."),
                ("not-in-room", "No screener, no chance. That is not taste. That is logistics."),
                ("same-five", "I could have written the list in July. The season is a ritual around a spreadsheet."),
            ),
        ),
        (
            "Snubs",
            "The annual identity fight: who got left off, and whether the body is a museum of its own taste.",
            (
                "A snub can be racism, provincialism, or math. The internet will pick one before the facts sit down.",
                "If the voter still cannot see international work, the category is a passport control.",
                "Outrage that only lasts a news cycle is still the only audit some of these rooms get.",
            ),
            (
                ("list-day", "They left her off and I believed the worst because the room has earned the worst."),
                ("passport", "If they need a subtitle, they need a miracle. That is the snub."),
                ("audit", "We are loud for 48 hours. They count on the 49th. Stay loud."),
            ),
        ),
        (
            "Box Office",
            "A grim accounting: awards bait that cannot sell a Tuesday, and a blockbuster that does not need a statue.",
            (
                "Prestige that cannot find an audience is not a moral victory. It is a closed loop.",
                "If the only movies that print money are sequels, the season is a museum attached to a mall.",
                "Gross is not quality. Gross is also not nothing when the crew needs a next job.",
            ),
            (
                ("tuesday", "It won the room and lost the zip code. Both facts are true."),
                ("mall-museum", "The statue went to a film 200,000 people saw. The mall went to part 7. We live in the mall."),
                ("next-job", "I like the art. I also like my mixer getting hired. Do not make me pick in public."),
            ),
        ),
        (
            "Craft",
            "Below-the-line people want the camera, the cut, the sound — the work that is not a celebrity's bone structure.",
            (
                "A season that cannot name a sound mixer is a season that does not know how a movie happens.",
                "Craft categories are not consolation. They are the reason the lead looks like a god.",
                "If the live show dumps craft to a pre-tape, the live show is a commercial with a host.",
            ),
            (
                ("sound", "She saved the scene. The host dumped her to a reel. I saw the reel. Hire a new host."),
                ("not-consolation", "The light is the performance. Say it in the big room."),
                ("pre-tape", "If it is not live, it is not the show. It is a courtesy. We notice."),
            ),
        ),
    ),
    "Fandom Wars": faces(
        (
            "Shipping",
            "Pairings as identity: a story people live in harder than the text, and a war when canon will not comply.",
            (
                "A ship is a reading. A campaign to make the studio comply is a different hobby.",
                "When pairing discourse is the only discourse, the work becomes a dollhouse and the dolls have stans.",
                "Creators who bait a ship for clicks and then dunk on the shippers built the fire they are calling crazy.",
            ),
            (
                ("dollhouse", "I just wanted two idiots to kiss. It became a jurisdiction. I left."),
                ("bait", "They sold the glance. Then they mocked the people who bought it. That is a business model."),
                ("reading", "Let people write the fic. Stop demanding a press release from the writer."),
            ),
        ),
        (
            "Leaks",
            "Spoilers as a moral panic and as a labor issue: who got hurt when the file walked out.",
            (
                "A leak can be a fan crime and a worker trying to get paid. Those are not the same story.",
                "Spoiler culture that ruins a room for sport is just another raid.",
                "If the only way to be first is to burn the surprise, the fandom has a metric problem.",
            ),
            (
                ("file-walked", "Someone on the chain needed rent. The timeline needed a scalp. Only one of those is a villain in my book."),
                ("raid-spoiler", "They dropped the ending in the main tag for the bit. The bit is cruelty."),
                ("first", "I can wait. The people who cannot wait are why we cannot have a night."),
            ),
        ),
        (
            "Harassment",
            "The part that is not cute: brigades, deepfakes, and a platform that calls it engagement.",
            (
                "A mass report campaign is not criticism. It is a tool.",
                "Actors are not the character. Forgetting that is how you get a security detail for a sitcom.",
                "If the platform ranks the pile-on, the platform is the pile-on.",
            ),
            (
                ("mass-report", "They taught a teenage fandom to SWAT a stranger with a form. Very online. Very real."),
                ("not-the-character", "She played a villain. They sent the funeral. I need a grown-up in the room."),
                ("ranker", "The app boosted the callout. Then it hid the apology. Engagement, they said."),
            ),
        ),
        (
            "Canon",
            "Who owns the story: the company, the showrunner, or the people who kept it alive in the desert years.",
            (
                "Canon is a tool. It is not a police. The police version is how you get a dead fandom.",
                "A reboot that overwrites the thing people loved without cause is a landlord renovation.",
                "Headcanon that stays on the fic site is peace. Headcanon that demands a firing is a coup.",
            ),
            (
                ("police", "Let the book be a book. I do not need a lore officer in my mentions."),
                ("reboot-reno", "They gutted the apartment and kept the name. That is not canon. That is a REIT."),
                ("coup", "Write your version. Leave the writer employed. Both are allowed."),
            ),
        ),
    ),
    "Comedy Scene": faces(
        (
            "Clubs",
            "Comics treat the room as the last honest note: two-drink minimums, a shrinking door, and a chain that wants a brand.",
            (
                "A club that is a TV set with a bar is not a laboratory. It is a content farm with stools.",
                "Door deals that cannot beat an open-mic gas bill will not grow a scene.",
                "If the chain owns the calendar, the city has a franchise, not a comedy scene.",
            ),
            (
                ("tv-stools", "They filmed the set and forgot the door. The door was the point."),
                ("gas-bill", "I drove two hours for $25. That is a hobby with a spotlight."),
                ("chain-cal", "The independent night moved to a Tuesday that does not exist. The chain had a coupon."),
            ),
        ),
        (
            "Specials",
            "Streaming specials as both a lottery ticket and a graveyard of mid-career hours that used to tour.",
            (
                "A special that pays like a clip and expects a film's prep is a bad contract with a brick wall.",
                "When the algorithm buries anything over 20 minutes, the hour is a luxury object.",
                "Selling the hour to a platform that will dump it in six weeks is how you burn a life cycle.",
            ),
            (
                ("clip-pay", "They paid me like a TikTok and asked for a film. I am not a charity with a stool."),
                ("20-min", "The hour still exists. The home screen does not believe in it."),
                ("six-weeks", "My life's work is a row between a true-crime thing and a baking show. Cute."),
            ),
        ),
        (
            "Cancel Talk",
            "The endless argument: punch down, punch up, and a clip that is the whole career in 19 seconds.",
            (
                "A crowd can say no. That is not a state. It is a room, which is the job.",
                "A pile-on that wants a firing for a bit that was already dying is not accountability. It is content.",
                "Comics who hide behind 'you can't say anything' while saying everything are doing a bit. Notice the bit.",
            ),
            (
                ("the-room", "If the room goes quiet, that is data. I can live with data. I cannot live with a prosecutor in the comments."),
                ("19-seconds", "The bit was bad. The campaign wanted a head. Only one of those is comedy."),
                ("can-too", "They say you cannot joke. They are joking while they say it. Watch the set, not the interview."),
            ),
        ),
        (
            "Podcasts",
            "The new club is a mic in a garage: direct money, rambling hours, and a pipeline that skips the road.",
            (
                "A podcast that never dies on a Tuesday in Cleveland will miss a muscle.",
                "Patreon is a club with better margins and worse hecklers — sometimes.",
                "When the comic is a media company, the jokes have to feed a machine. Machines are hungry.",
            ),
            (
                ("cleveland", "I still want the room that can fire me in real time. The garage cannot."),
                ("patreon-club", "They pay me to ramble. I try to earn it. Some weeks I do not."),
                ("machine", "Three episodes a week is a factory. I miss two jokes a night and a Friday."),
            ),
        ),
    ),
    "Theater Revival": faces(
        (
            "Touring Costs",
            "Road companies describe trucks, hotels, and a guarantee that no longer closes.",
            (
                "If the split cannot clear diesel, the road is a luxury of the brands that can print merch.",
                "A non-Equity tour that uses the Broadway name is a bait for towns that do not see the contract.",
                "Presenters who only buy the tourist title will starve the play that would have built an audience.",
            ),
            (
                ("diesel", "The truck won. The actor lost. That is the tour."),
                ("name-bait", "They sold 'direct from Broadway'. The contract was direct from a van. The town deserved the sentence."),
                ("tourist-title", "Cats again. The new play can die in a classroom. Very brave programming."),
            ),
        ),
        (
            "Broadway",
            "The island as a luxury good: dynamic orchestra, tourist armor, and a labor fight under the marquee.",
            (
                "A $700 orchestra seat is not a popular art. It is a hedge-fund night with a pit.",
                "If locals cannot go, the form is a museum that happens to sing.",
                "Labor in the house is the show. A producer who forgets that will learn on a dark night.",
            ),
            (
                ("700-row", "I saw it from the last row I could stand. The empty luxury seats were the set."),
                ("locals", "My city has a street of theaters I cannot afford. That used to be a punchline."),
                ("dark-night", "Pay the pit. I would like there to be a pit."),
            ),
        ),
        (
            "School Plays",
            "Teachers treat the musical as the last public arts budget: the auditorium, the rights, and a kid who found a self.",
            (
                "Rights that cost more than the set are how a catalog becomes a gate.",
                "Cutting the drama teacher is a literacy cut. Bodies in a play still have to read.",
                "A community that will fund a football clock and not a curtain is making a taste argument with money.",
            ),
            (
                ("rights-gate", "We can do the show if we skip the chorus. The chorus is the town's kids. Cute."),
                ("drama-cut", "She taught 140 kids to speak in public. We kept the turf. The turf does not speak."),
                ("clock", "The board found the scoreboard. It could not find a wireless pack. I filed that away."),
            ),
        ),
        (
            "Grants",
            "Small companies live on a cycle of PDFs: city arts, a foundation, and a board that wants a gala.",
            (
                "A grant that takes 40 hours to miss is a second job with worse pay.",
                "General operating is the only honest money. Project grants make you invent a project you cannot staff.",
                "If the city wants a scene, it has to buy rent, not a one-night activation.",
            ),
            (
                ("40-hours", "I wrote a novella for $2,500 I did not get. That is the arts economy."),
                ("go-please", "Stop making me invent a youth-engagement appendix. Pay the lights."),
                ("activation", "They want a pop-up. I want a lease. Only one of those is a theater."),
            ),
        ),
    ),
    "Reality TV": faces(
        (
            "Labor",
            "Contestants and crew describe a set that is a job without being called one: hours, NDAs, and a stipend that is a joke.",
            (
                "If you cannot leave without a lawyer, you are not a guest. You are staff.",
                "A $1,000/week 'experience' on a 16-hour set is a wage story.",
                "Unionizing the unscripted crew is how you stop a producer from being a weather system.",
            ),
            (
                ("ndas", "I cannot tell you what happened. I can tell you I was not a volunteer."),
                ("stipend", "They called it a prize journey. Payroll would have called it overtime."),
                ("weather", "The producer is the climate. I would like a contract that works in rain."),
            ),
        ),
        (
            "Editing",
            "Frankenbites and villain edits as the actual writing staff — consent that ended at the release form.",
            (
                "A cut that invents a sentence is not storytelling. It is a deepfake with a union editor, sometimes.",
                "People who go home to a town that saw a cartoon of them are the externality.",
                "If the show needs a villain more than a record, it should hire an actor and call it fiction.",
            ),
            (
                ("franken", "I did not say that sentence. The sentence is famous. That is the craft."),
                ("town", "The grocery still thinks I am the edit. The edit was a job I did not have."),
                ("hire-actors", "Stop asking civilians to be characters. Pay characters."),
            ),
        ),
        (
            "Fame Pipeline",
            "The show as an audition for influencing: 15 weeks, a follow count, a supplement deal.",
            (
                "When the prize is a brand, the show is a factory for people who will sell a powder.",
                "A pipeline that only works if you stay recognizable will punish anyone who wants a normal Tuesday.",
                "Audiences can smell an audition. That is why the older seasons feel like a documentary of a stranger planet.",
            ),
            (
                ("powder", "Nobody wants the money. They want the handle. The handle wants a SKU."),
                ("tuesday", "She cannot go to Target. That was the prize. Look at it."),
                ("old-seasons", "They did not know what they were yet. Now everybody knows. It is less interesting."),
            ),
        ),
        (
            "Products",
            "Integration as the secret season: a bottle, a car, a slot that is why the episode exists.",
            (
                "A challenge designed around a logo is an infomercial with tears.",
                "If the prize is a coupon, the show should air at 3am with a 1-800 number.",
                "Viewers who skip the integration are why the next one will be louder, not quieter.",
            ),
            (
                ("logo-challenge", "They built an obstacle out of a soda. I built an exit out of the episode."),
                ("coupon-prize", "The winner got a year's supply. The network got a quarter. Guess who is the customer."),
                ("louder", "I fast-forwarded. They put it in the confessionals. There is no peace."),
            ),
        ),
    ),
}
