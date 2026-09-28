"""Economy extras beyond Housing Costs and Labor Markets."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Inflation Fight": faces(
        (
            "Grocery Bills",
            "Households treat the receipt as the inflation index that matters — eggs, meat, and the shrinking package.",
            (
                "A CPI print that excludes the aisle you actually walk is a press conference, not a budget.",
                "Shrinkflation is a price increase that hopes you will not do the unit math.",
                "When grocery takes a bigger bite than rent growth, 'transitory' is a word from another income.",
            ),
            (
                ("unit-price", "The box is shorter. The number is not. I did not get dumber. The package did."),
                ("egg-math", "They told me inflation cooled. My cart did not get the memo."),
                ("ebt-gap", "Benefits lag the aisle by months. That lag is a policy, not a rounding error."),
            ),
        ),
        (
            "Rate Hikes",
            "This cluster reads the Fed as a blunt instrument: rents and mortgages take the punch while the grocery aisle shrugs.",
            (
                "Higher rates are a housing and hiring tool pretending to be a grocery tool.",
                "People with credit-card float are already in a recession. The print can catch up later.",
                "A soft landing that shows up as a locked millennial buyer is a landing for someone else.",
            ),
            (
                ("mortgage-lock", "I am not overheated. I am 7%. Stop cooling me."),
                ("card-apr", "The grocery fight is on the revolving statement. That is the rate that hits first."),
                ("small-loan", "The plant delayed the expansion. The aisle did not notice. Different economies."),
            ),
        ),
        (
            "Corporate Margins",
            "A louder thread says firms kept the pandemic price and called it costs — concentration made the excuse stick.",
            (
                "If input costs fell and the shelf did not, that is not a commodity story. It is a market-power story.",
                "Three firms and a 'regretfully' email is how a nation gets lectured about greed by a press release.",
                "Profits as a share of price are the receipt economists were late to read and shoppers were not.",
            ),
            (
                ("margin-call", "Their 10-K is having a great year. My chicken is not. Reconcile that without the word 'consumer'."),
                ("shelf-power", "There is one brand of oats that is three brands. That is why the price stuck."),
                ("fee-creep", "They unbundled the bag, the bottle, and the lid, and called it inflation."),
            ),
        ),
        (
            "Wage Lag",
            "Workers keep stacking raises against the cart and calling the remainder a disappearance, not a print.",
            (
                "A 4% raise after a 9% aisle is a pay cut with a cake in the break room.",
                "Real wages that recover 'on average' still lose in the zip codes that buy diesel and rent.",
                "Contract lags are the point of some businesses. Inflation just made the lag visible.",
            ),
            (
                ("cola-none", "Our contract has no COLA. Their prices have a habit. That is the fight."),
                ("tip-math", "They added a service fee and froze the wage. Inflation for thee.",),
                ("real-check", "BLS says I am catching up. My leftover after groceries is the audit I trust."),
            ),
        ),
    ),
    "Small Business": faces(
        (
            "Rent and Cards",
            "Owners treat occupancy costs and swipe fees as the silent partners who never miss a draw.",
            (
                "A landlord who resets to 'market' after you built the foot traffic is extracting the brand you paid to invent.",
                "Two-and-a-half percent plus a new 'per-item' nonsense is a private sales tax with a terminal.",
                "Delivery apps that own the customer and the fee stack are a second landlord on the same square footage.",
            ),
            (
                ("lease-reset", "I made the block busy. The rent noticed. I am paying for my own foot traffic twice."),
                ("swipe-tax", "The card networks take more than my electrician. They did not hang a single fixture."),
                ("app-cut", "We are a ghost kitchen for a logo that charges us to speak to our own tables."),
            ),
        ),
        (
            "Hiring",
            "Main-street shops describe help-wanted as a math problem: wages the register cannot clear, and applicants who cannot clear the rent.",
            (
                "If the wage that keeps a closer needs a price the block will not pay, the business model is the shortage.",
                "'Nobody wants to work' usually means nobody wants this shift at this number with this commute.",
                "A help-wanted sign that has been up a year is a price signal. Take it.",
            ),
            (
                ("close-early", "We close at 7 now. Not a vibe. A body count. I cannot staff the last two hours at $14."),
                ("apply-ghost", "Forty applications, three showings, one hire who lasted a week. The apartment two towns over won."),
                ("tip-pool", "I can raise menu prices or I can keep neighbors. The labor market wants me to pick."),
            ),
        ),
        (
            "Main Street",
            "This view is about the block as a civic good: vacant storefronts, empty upstairs, and a downtown that is a parking plan.",
            (
                "A downtown of vape shops and ghost leases is a tax-base problem before it is an aesthetic one.",
                "If the upstairs cannot be an apartment, the shop downstairs will keep dying at 6pm.",
                "Chain incentives that hollow the square and then ask the chamber to 'activate' it are a loop.",
            ),
            (
                ("dark-windows", "Six empties on Main and a ribbon-cutting at the outlet mall. That is the industrial policy."),
                ("upstairs", "We could house people over the shop if the code remembered how mixed-use works."),
                ("park-first", "The plan is more parking. The problem is nobody lives close enough to walk after work."),
            ),
        ),
        (
            "Platform Fees",
            "Sellers treat Amazon, Etsy, and Square as utilities that change the split whenever the weather is good.",
            (
                "A marketplace that is also the competitor, the ad auction, and the cop is not a mall. It is a company town.",
                "Buy Box games and forced ads are a wage cut for people who thought they owned a shop.",
                "Owning your customer list is the whole business. Renting it back from a platform is a hobby.",
            ),
            (
                ("buy-box", "I won the search until I declined the ad. Then I was a ghost in my own listing."),
                ("etsy-cut", "They raised the take, added ads, and sent a blog post about community. I blocked the word community."),
                ("own-list", "The day Square hid the emails was the day I understood I was a stall, not a store."),
            ),
        ),
    ),
    "Trade Wars": faces(
        (
            "Tariffs",
            "Importers and shoppers treat the new duties as a sales tax with a flag on it, paid at the register not the port.",
            (
                "A tariff is a domestic price. Pretending the foreign exporter eats it is a speech, not an invoice.",
                "Line-by-line exemptions are industrial policy by lobbyist. Everyone else gets the list price.",
                "Retaliation lands on the crop and the factory that were not in the room for the announcement.",
            ),
            (
                ("landed-cost", "We paid the duty, raised the SKU, and watched the competitor with a carve-out smile."),
                ("washer-memory", "Last time the machines jumped and never came back. I kept the receipt."),
                ("flag-tax", "If it is a tax, vote on a tax. Do not hide it in a 10,000-line list."),
            ),
        ),
        (
            "Factory Moves",
            "This cluster is about firms hopping from one 'plus-one' country to the next — diversification as a PowerPoint, disruption as a town.",
            (
                "A ribbon-cutting in a new country is a funeral in the old one. Count both.",
                "Friend-shoring that still needs the same critical part from the same choke point is a sticker, not a chain.",
                "Workers are not a slide labeled 'flex'. They are the inventory that cannot be containerized.",
            ),
            (
                ("plus-one", "We left one coast for another and called it resilience. The jig and the know-how did not all fit in the crate."),
                ("tooling", "The line is gone. The tooling drawings are in a Dropbox. That is not a manufacturing base."),
                ("town-hall", "They thanked us for 40 years and left a training grant. The grant does not punch in."),
            ),
        ),
        (
            "Farm Exports",
            "Growers treat soy, pork, and sorghum as the hostage in every diplomatic mood swing.",
            (
                "A bin that cannot move is a price collapse with a lag. The loan officer does not wait for the next round.",
                "Export markets that took a decade to open can close in a tweet. That asymmetry is the job risk.",
                "Aid checks after the fact are not a market. They are an apology with a farm number.",
            ),
            (
                ("basis-hit", "The buyers vanished in a week. The rent did not. That is a trade war on a county road."),
                ("silo-full", "I stored it, prayed, and watched the basis go feral. Diplomacy is a moisture reading now."),
                ("check-later", "The aid landed after I sold low. Timing is the whole program."),
            ),
        ),
        (
            "Chip Supply",
            "Manufacturers describe lead times as the real tariff: you cannot assemble what is on allocation.",
            (
                "A 52-week microcontroller is industrial policy whether anyone voted on it or not.",
                "Dual-sourcing a chip that only one fab still runs is a bedtime story for the board.",
                "Cars, dishwashers, and ventilators wait in the same line. Consumer and capital goods are one bottleneck now.",
            ),
            (
                ("mcu-wait", "The board is $2. The delay is a quarter. We redesigned around a chip from 2011 like it was a war."),
                ("auto-lot", "Finished trucks, missing a $4 part. That is the modern factory: a parking lot of almost."),
                ("alloc", "Our allocation shrank so a bigger logo could make more. The market is a handshake."),
            ),
        ),
    ),
    "Care Economy": faces(
        (
            "Childcare",
            "Parents and providers treat infant care as infrastructure that the labor market pretends is a private hobby.",
            (
                "A slot that costs more than in-state tuition is the first tax on having a second earner.",
                "Providers leaving for Target wages is not a mystery. It is the price of a job with no benefits and someone else's toddler.",
                "Without public money, the market rations care to people who already have a grandmother or a trust.",
            ),
            (
                ("infant-math", "Two kids in care is a mortgage. One of us left the job. That is the labor-force participation print."),
                ("center-close", "We paid teachers $14 to do the hardest work in town. They went to the warehouse. Shocked, I am."),
                ("wait-18", "Pregnant and 18th on the list. The economy starts before labor, and it waitlists you."),
            ),
        ),
        (
            "Home Health",
            "Aides describe the job as a driving tour of other people's aging, paid like errands, billed like medicine.",
            (
                "A 15-minute visit that includes a highway is not care. It is a logistics stunt with a blood-pressure cuff.",
                "Medicaid rates that cannot clear gas and time will keep producing a shortage and a speech about dignity.",
                "The family still does the night shift. The agency does the invoice.",
            ),
            (
                ("seven-houses", "Seven clients, one tank of gas, no paid lunch. I am the health system for people the hospital discharged 'stable'."),
                ("rate-card", "The state pays me less per hour than the parking. Dignity is not in the rate.",),
                ("night-family", "We leave at 6. The daughter takes over at 6:01. That is the real staffing model."),
            ),
        ),
        (
            "Unpaid Hours",
            "This cluster names the granddaughter, the spouse, and the neighbor as the largest care workforce — off the books on purpose.",
            (
                "GDP that ignores unpaid care is a map with the biggest sector erased.",
                "A 'sandwich generation' is a policy failure with a cute name.",
                "Leave that is job-protected but unpaid is a right only people with savings can use.",
            ),
            (
                ("sandwich", "I am HR, a daughter, and a mother before 9am. None of that is in the employment report."),
                ("fmla-zero", "I qualified for leave I could not afford. That is a brochure right."),
                ("neighbor-meds", "The block does the meds. Medicare does the paperwork. Guess which one keeps him home."),
            ),
        ),
        (
            "Public Options",
            "Advocates want a public floor — universal pre-K that lasts past 2pm, home-care benefits, and a wage that is not a tip jar.",
            (
                "A market that cannot price infant care without burning out the worker is asking the state to be the employer of last resort. Fine.",
                "Tax credits that assume a spare $12,000 are a gift to people who already found a slot.",
                "If care is infrastructure, build it like a road: public, boring, and open at hours people work.",
            ),
            (
                ("pre-k-2pm", "Universal until 2pm is a press conference. I work until 5. Hire the afternoon or stop saying universal."),
                ("credit-gap", "The credit arrives in April. The slot was due in September. Timing is the benefit."),
                ("public-aide", "Put home care on a public payroll with a pension. The 'market' already told us the price."),
            ),
        ),
    ),
    "Wall Street": faces(
        (
            "Index Funds",
            "A skeptical cluster treats the S&P as a voting machine for three asset managers — cheap for savers, concentrated for everyone else.",
            (
                "Passive is not apolitical. It is a default vote for whatever is already large.",
                "Fee compression for households is real. So is a governance bottleneck nobody elected.",
                "When the same three files vote every board, 'market discipline' is a staff memo in a tall building.",
            ),
            (
                ("vote-three", "My 401k is thrifty and my country is owned by a committee I cannot email."),
                ("mega-cap", "The index is a momentum machine for five logos. Diversification is a story we tell target-date funds."),
                ("proxy-season", "They voted with management. They always vote with management. That is the product."),
            ),
        ),
        (
            "Buybacks",
            "Critics read buybacks as the corporate purpose: juice the per-share number, starve the shop floor, call it returning capital.",
            (
                "A firm that borrows to shrink its share count is not investing. It is financial engineering with a press release.",
                "If the capital were truly excess, wages and maintenance would not look like this.",
                "Executives paid in stock have a hobby. It rhymes with repurchase.",
            ),
            (
                ("auth-board", "They authorized $20B and froze hiring. Returning capital, they said, to people who already have it."),
                ("eps-cult", "The machine is old. The EPS is young. Guess which one they oiled."),
                ("grant-then-buy", "Issue stock to the C-suite, buy it back from the market. Perpetual motion for compensation."),
            ),
        ),
        (
            "Bank Rules",
            "This view is still 2008 in muscle memory: capital, liquidity, and the quiet dump of the uninsured when a mid-size name wobbles.",
            (
                "Deregulation that shows up as a weekend sale is not efficiency. It is a put the public did not price.",
                "Living wills nobody believes are literature. Loss-absorbing capital is the chapter that matters.",
                "A mid-size bank that is systemic in one metro is still systemic. The spreadsheet should notice the metro.",
            ),
            (
                ("weekend-sale", "They called it idiosyncratic. Then they guaranteed everyone. I wrote that down."),
                ("sifi-lite", "We are too small to be careful and too local to fail. Cute category."),
                ("capital", "If the rule is a burden, so is the bailout. Pick the cheaper burden while it is still a memo."),
            ),
        ),
        (
            "Retail Traders",
            "A mixed cluster treats the app as both a democratized ticker and a casino that learned how to ping dopamine.",
            (
                "Zero commissions were paid for in order flow and attention. The price of the trade is the feed.",
                "Meme common-sense sometimes finds a real squeeze. It also finds a lot of bags.",
                "If the interface looks like a game, it will be played like one. That is not an accident.",
            ),
            (
                ("confetti", "The app threw confetti at a $40 gain and hid the 1099. That is a design choice."),
                ("squeeze-chat", "We were right for a week and a punchline for a year. Still more honest than the desk that sold us the dip."),
                ("order-flow", "My order went to a wholesaler. I am the product with a ticker."),
            ),
        ),
    ),
    "Student Economy": faces(
        (
            "Side Gigs",
            "Students describe DoorDash and campus shifts as the hidden financial-aid office.",
            (
                "A full-time courseload plus 25 hours of deliveries is not grit. It is a hole in the package.",
                "Gig apps love campuses because the labor is desperate, insured by parents or not at all.",
                "When 'work-study' pays 2008 wages, the side gig is the real study.",
            ),
            (
                ("dash-finals", "I wrote the midterm in a parking lot between pings. That is the learning environment."),
                ("package-gap", "They called it unmet need. I called it Thursday night in a Civic."),
                ("work-study", "The campus job is $9. The app is worse and faster. I picked worse and faster."),
            ),
        ),
        (
            "Campus Work",
            "This cluster wants dining halls, libraries, and rec centers to stop being the unpaid intern economy of the university.",
            (
                "A billion-dollar endowment and a dining-hall wage that needs tips is a values statement.",
                "International students trapped in on-campus hours are a captive labor pool. Name it.",
                "When the union card shows up in the dish room, that is the market talking.",
            ),
            (
                ("dish-line", "I feed 4,000 people and qualify for the food pantry. That is the brand."),
                ("visa-hours", "I cannot work off campus. They know. The schedule knows. The wage knows."),
                ("card-check", "We asked for a living wage and got a pizza party. Then we asked again with a card."),
            ),
        ),
        (
            "Loan Math",
            "Borrowers treat origination, interest, and servicer portals as a second major nobody graded.",
            (
                "Interest that starts while you are still in the seat is how a 'help' becomes a balance.",
                "Income-driven plans that take a graduate degree to understand are a maze with a penalty for the lost.",
                "Parent debt in the student's name is a family business with no limited liability.",
            ),
            (
                ("servicer-bot", "I have a portal, a second portal, and a balance that does not match. That is the product."),
                ("accrual", "They called it aid. It started compounding at orientation. Cute word, aid."),
                ("plus-trap", "My mom is on the hook until she dies. That was not in the yield-day packet."),
            ),
        ),
        (
            "First Apartments",
            "New graduates describe deposits, roommates, and 'young professional' rent as the actual commencement.",
            (
                "A first job that cannot clear a studio is not an entry wage. It is a roommate sentence.",
                "Broker fees and 3x income tests are a gate in front of the degree the university already sold.",
                "Moving home is not a failure. It is an implicit housing subsidy the statistics file under 'family'.",
            ),
            (
                ("3x-rent", "I make the 'good' salary. I do not make 3x this studio. The algorithm does not care about my diploma."),
                ("broker-tax", "Fifteen percent to a person who emailed a PDF. Welcome to the city."),
                ("home-again", "I moved back at 23. The commencement speech did not cover this unit."),
            ),
        ),
    ),
    "Crypto Winter": faces(
        (
            "Exchange Failures",
            "Customers treat collapsed venues as the lesson: not your keys, not your coins, and sometimes not your lawsuit.",
            (
                "A platform that is a bank, a broker, and a hedge fund is a conflict with a logo.",
                "Bankruptcy queues are the consumer-protection regime. That should have been the warning label.",
                "Yield that needs a new depositor is not DeFi. It is a story with a QR code.",
            ),
            (
                ("not-your-keys", "They had a skip-the-line program for friends. I had a FAQ. That was the product."),
                ("claim-form", "I am a creditor now. I used to be a customer. The winter was a legal category."),
                ("audit-pdf", "The proof of reserves was a screenshot. I want that carved on the courthouse."),
            ),
        ),
        (
            "Stablecoins",
            "This view treats dollars-on-chain as useful pipes — and as runs waiting for a reserve that is not a slide.",
            (
                "A peg is a promise about reserves. If the reserve is 'cash-like', say the CUSIPs.",
                "Payments that settle on a weekend are real. So is a redemption gate.",
                "A run in a coin used as wages in another country is a monetary-policy accident with a chatroom.",
            ),
            (
                ("cusip-please", "Show me T-bills or stop saying fully backed. I can read a footnote."),
                ("weekend-wire", "I paid a supplier on Sunday. That part is not a joke. The attestations still are."),
                ("off-shore-pay", "People take wages in this. Treat it like money or stop letting it pretend."),
            ),
        ),
        (
            "True Believers",
            "A stubborn minority still wants self-custody, public rails, and an exit from banks that freeze first and explain later.",
            (
                "The scams do not retire the case for a bearer instrument that a compliance officer cannot quietly freeze.",
                "Self-custody is user-hostile on purpose. That hostility is the point for people who have been deplatformed.",
                "If your politics needs a permissioned ledger, you wanted a database. Say database.",
            ),
            (
                ("seed-phrase", "I lost friends to casinos and still will not give a bank a kill switch over my rent money."),
                ("frozen-wire", "They froze the donation. The chain would not have. That sentence is the whole religion."),
                ("l2-fees", "Fees are ugly. A permissioned 'innovation' sandbox is uglier."),
            ),
        ),
        (
            "Regulation",
            "Policy people want a rulebook that is not 100 enforcement actions and a wink — bank, commodity, or joke, pick one.",
            (
                "Regulation by surprise is how you get lawyers rich and users rugged.",
                "A consumer token with no disclosures is a security in every sense except the one that would have helped.",
                "Clear custody rules would have saved more people than a Senate hearing with a prop.",
            ),
            (
                ("enforcement", "They sued the ones that survived. The ones that fled took the deposits. Sequencing is the policy."),
                ("disclosure", "I wanted a risk factor. I got a cartoon ape. That is the gap a form could have filled."),
                ("custody-rule", "Tell me who is a bank. Then I will know who to hang when it breaks."),
            ),
        ),
    ),
    "Public Debt": faces(
        (
            "Interest Costs",
            "Budget hawks treat net interest as the program that ate the rest — a line that grows without a ribbon-cutting.",
            (
                "A dollar of interest is a dollar that will not be a bridge, a lab, or a child tax credit.",
                "Rolling cheap pandemic debt into a higher-rate world is how a past emergency taxes the present.",
                "If the fastest-growing 'program' is interest, the politics will get uglier than any discretionary fight.",
            ),
            (
                ("net-interest", "We are funding the past at 5%. The future can wait in committee."),
                ("roll", "The cheap bonds expired. The speeches did not. That is the bill."),
                ("crowding", "Tell me what we cut when the interest line passes defense. Nobody wants to audition."),
            ),
        ),
        (
            "Ceiling Fights",
            "This cluster reads the debt limit as a hostage ritual that raises the risk premium for a press hit.",
            (
                "Threatening default to win a budget point is arson in a shared house.",
                "Markets price the ritual now. That price is paid by everyone who is not in the room.",
                "If you want spending cuts, vote for spending cuts. Do not dress them as a solvency dare.",
            ),
            (
                ("x-date", "We did this again. The bill for the stunt is in the next auction. Cute."),
                ("14th", "Do not make a constitutional crisis out of an already-spent appropriation. Pay the invoice."),
                ("risk-premia", "My town's hospital loan moved because a caucus needed a clip. That is the ceiling."),
            ),
        ),
        (
            "Austerity",
            "Opponents say the 'belt-tightening' always finds the grant, the clinic, and the bus — never the preference that is harder to name.",
            (
                "Austerity is a distributional choice that pretends to be weather.",
                "Cutting the visible service to save a quiet tax expenditure is how you teach people to hate government.",
                "If the debt is the crisis, the menu should include revenue. A menu with only buses is a tell.",
            ),
            (
                ("bus-cut", "They saved the carryforward and lost the Sunday route. The debt did not notice. The shift workers did."),
                ("clinic-line", "Austerity arrived as a closed WIC window. Very brave."),
                ("menu", "I will take the deficit seriously when the spreadsheet includes the loophole with a trade association."),
            ),
        ),
        (
            "Tax Base",
            "This view wants the conversation on who is in the base: capital gains, shelters, and firms that live nowhere.",
            (
                "A base that is wages plus a few retail sales will always look 'unable' to fund the state it voted for.",
                "Pass-through games and profit-shifting are the deficit in costume.",
                "Broaden, then argue about the rate. Arguing about the rate on a hole is theater.",
            ),
            (
                ("nowhere-corp", "The profits are in a letterbox. The potholes are here. That is the base."),
                ("cap-gains", "Work is taxed on payday. Wealth is taxed on a vibe and a lobbyist."),
                ("broaden", "I do not want a new gimmick. I want the income we already agreed was income."),
            ),
        ),
    ),
}
