"""Environment extras beyond Climate Policy."""

from pipeline.demo_briefs.format import faces

BRIEFS = {
    "Water Crisis": faces(
        (
            "Aquifers",
            "Farmers and hydrologists treat groundwater as a bank account everyone is overdrawing, with a lag measured in decades.",
            (
                "A well that drops a foot a year is a policy. The aquifer is just keeping the books.",
                "Permits that assume last century's recharge are a fiction with a pump.",
                "Once the clay collapses, the storage is gone. That is not a drought. That is a demolition.",
            ),
            (
                ("well-log", "My grandfather's well is a museum. Mine is a race. The water district sent a brochure."),
                ("recharge-lie", "The permit still thinks it rains like 1952. It does not."),
                ("subsidence", "The ground fell. The storage fell with it. There is no stimulus check for that."),
            ),
        ),
        (
            "City Rations",
            "Urban users meet the shortage as a stage: lawn days, hotel exemptions, and a fine that never finds the golf course.",
            (
                "A ration that hits the renter's shower and skips the ornamental lake is a class policy.",
                "Indoor use is not the leak. Outdoor ornament is. The stage should match the data.",
                "If the city cannot recycle wastewater, it is choosing the next drought.",
            ),
            (
                ("lawn-day", "I got fined for a tomato. The median still glows. Cute ration."),
                ("hotel-green", "Tourism is an exemption. My kid's schoolyard is dust. Say the quiet part."),
                ("purple-pipe", "We could drink the treated stuff. We argue about the word instead."),
            ),
        ),
        (
            "Farm Wells",
            "Growers argue they feed people with that water — and that fallowing without a transition is a hunger plan dressed as conservation.",
            (
                "A crop that is 90% exported water is not food security. It is a pipeline with leaves.",
                "Fallow payments that miss tenants and pickers are a landlord program.",
                "Efficiency without a cap just grows more acres. The aquifer still loses.",
            ),
            (
                ("almond-math", "I grow calories and I grow a shipping container of water. Be honest about which invoice you want.",),
                ("tenant-dry", "The owner took the fallow check. I lost the lease. Conservation, they called it."),
                ("drip-then-expand", "We installed drip and planted more. The well did not clap."),
            ),
        ),
        (
            "Pipe Lead",
            "This cluster is still Flint in muscle memory: the last mile of pipe as a civil-rights file, not a plumbing footnote.",
            (
                "A filter on a kitchen tap is not a system. It is an apology you have to remember to change.",
                "Replacing service lines without paying the homeowner's last six feet is how the map stays red.",
                "Corrosion control that is a memo, not a chemical feed, is how you get a generation of blood tests.",
            ),
            (
                ("filter-stack", "We have a pitcher, a tap, and a distrust. The city has a press release."),
                ("last-six", "They dug the street and stopped at my property line. Lead does not honor property lines."),
                ("blood-lead", "The kids failed the test. The pipes passed the politics. That is the split."),
            ),
        ),
    ),
    "Grid Transition": faces(
        (
            "Baseload",
            "Operators want something that runs at 2am in January besides a prayer and a gas peakers' invoice.",
            (
                "A grid that only works when the weather is polite is a hobby.",
                "Calling gas 'bridge' for 30 years is how a bridge becomes a destination.",
                "If you shut firm power before firm power exists, you have exported the carbon and imported the blackout.",
            ),
            (
                ("jan-2am", "Show me the 2am plan that is not a gas turbine and a tweet. I am listening."),
                ("bridge-forever", "The bridge opened in 1994. It is a highway now."),
                ("firm", "I will cheer the retirement when the replacement has a name and a transformer on order."),
            ),
        ),
        (
            "Batteries",
            "This view treats storage as the actual renewable plant — four hours is not a season.",
            (
                "A battery that covers sunset is progress. A battery that covers a wind drought is still a slide.",
                "Siting, fire codes, and mineral supply are the project. The chemistry is the easy paragraph.",
                "Pairing storage with a congested interconnection queue is how you get a very expensive fence.",
            ),
            (
                ("four-hours", "We bought sunset. Winter still exists. Do not call it solved."),
                ("fire-code", "The chemistry is fine. The setback is a year. That is the plant."),
                ("minerals", "We moved the smoke from the stack to a pit in another country. Honesty, please."),
            ),
        ),
        (
            "Interconnects",
            "Developers describe the queue as the real climate policy: five years to study a line that the politics may still kill.",
            (
                "Cheap electrons that cannot get on the wire are a press release.",
                "A queue that is a speculation market will stay a speculation market until you charge for the studies like you mean it.",
                "Transmission is land, courts, and governors. The engineering was never the bottleneck.",
            ),
            (
                ("queue-year-7", "My solar farm is a PDF in a pile. The gas plant already has a meter."),
                ("spec-queue", "They entered 10 ghost projects to hold a place. The ISO is a ticket scalper now."),
                ("line-hearing", "The electrons are easy. The county is not. Build the hearing into the Gantt chart."),
            ),
        ),
        (
            "Ratepayers",
            "Households meet the transition as a rider on the bill — wildfire liability, new substations, and a 'grid of the future' fee.",
            (
                "A just transition that shows up as a 19% delivery charge will lose the living room.",
                "If data centers want the next substation, they should sit on the invoice, not the apartment down the feeder.",
                "Shutoffs as a wildfire plan are how you socialize a utility's land management onto a medical-baseline customer.",
            ),
            (
                ("rider", "The generation got cheaper. The bill did not. The difference is a story about poles and lawyers."),
                ("campus-sub", "The training campus got a feeder. My neighborhood got a lecture about LEDs."),
                ("psps", "They cut me to save a tree they did not trim. I have oxygen. That is not resilience. That is a memo."),
            ),
        ),
    ),
    "Air Quality": faces(
        (
            "Wildfire Smoke",
            "Parents treat AQI as a season: canceled recess, DIY filters, and a sky that makes the climate report local.",
            (
                "A generation that learns colors before birds is living in a different country than the one that wrote the standard.",
                "Indoor air is now a public-health system. Schools without filtration are a policy.",
                "Prescribed fire and power-line maintenance are the boring cousins of this emergency. Fund them like emergencies.",
            ),
            (
                ("recess-red", "We canceled recess again. The worksheet said 'outdoor play builds character'."),
                ("box-fan", "Our HVAC is a box fan and a furnace filter. That is the adaptation plan."),
                ("prescribed", "They underfunded the burn crew for a decade. Then they discovered smoke. Cute."),
            ),
        ),
        (
            "Ports",
            "Near-port neighborhoods still breathe diesel while the rest of the map talks about EVs.",
            (
                "Electrifying last-mile vans and leaving the yard diesel is how you keep a sacrifice zip code.",
                "Idling ships are a power plant that does not need a permit the neighbors can find.",
                "If freight is the economy, the air in the first mile is the invoice.",
            ),
            (
                ("yard-kids", "The trucks shift-change at 3am. The asthma clinic opens at 8. That is a schedule."),
                ("shore-power", "They could plug in. They run the auxiliary. The air is a choice."),
                ("first-mile", "Your two-day shipping is my black carbon. Put that on the box."),
            ),
        ),
        (
            "Asthma",
            "Clinicians and parents treat inhalers, ER nights, and school nurses as the human AQI sensor.",
            (
                "An inhaler that triples in price during fire season is a second disaster.",
                "A school nurse for 900 kids is not a medical plan. It is a hope with a cot.",
                "Housing next to a freeway is an exposure. Zoning that keeps putting it there is intent.",
            ),
            (
                ("inhaler-price", "The sky went orange and the copay went feral. That is not coincidence. That is a market."),
                ("nurse-900", "I am the asthma plan. I am also lunch and a broken arm. Send a body."),
                ("freeway-housing", "They called it affordable. They meant downwind."),
            ),
        ),
        (
            "Diesel",
            "This cluster still wants the old villain in the dock: school buses, generators, and a freight fleet that is not a Tesla ad.",
            (
                "A child on a 1998 bus is an exposure we already know how to end.",
                "Backup diesel that becomes everyday generation in a heat wave is a loophole with a stack.",
                "Biofuel stickers on the same exhaust are not a cleanup.",
            ),
            (
                ("bus-1998", "Electrify the buses first. The pickup can wait. Lungs cannot."),
                ("gen-set", "The warehouse 'peaker' is a diesel farm with a nicer fence."),
                ("sticker", "They put a plant on the tank and left the NOx. I can read a tailpipe."),
            ),
        ),
    ),
    "Biodiversity": faces(
        (
            "Extinctions",
            "Field people talk about quiet losses — insects, mussels, a frog — that never make the charismatic-megafauna poster.",
            (
                "A collapse in insects is a collapse in everything that eats, pollinates, or decomposes. The owl is the press kit.",
                "Triage is already happening. Pretending we can save every species is how we save the logo and lose the rest.",
                "The rate is the story. A museum of what used to be here is not a policy.",
            ),
            (
                ("windshield", "I remember bugs. My kid thinks a clean windshield is normal. That is data."),
                ("triage", "We cannot do 12,000 recovery plans. We can do habitats. Pick."),
                ("mussel", "No one will march for a mussel. The river still needs it. So do we."),
            ),
        ),
        (
            "Land Trusts",
            "This view treats easements and local trusts as the actual conservation machine — slower than a tweet, stickier than a park bill.",
            (
                "A trust that pays a rancher to stay a rancher can beat a paper park that the next legislature sells.",
                "Easements that lock injustice in place are not a win. Read who got paid to not develop.",
                "If the land is conserved in a file cabinet, it is not conserved. Staff the stewards.",
            ),
            (
                ("easement", "We kept the grass and the cattle and the view. The condo lost. That is a policy I can touch."),
                ("who-paid", "The trust bought silence from a family that already had options. The other family got the highway."),
                ("steward", "The deed is forever. The intern is until August. Fund the forever."),
            ),
        ),
        (
            "Invasives",
            "Crews describe the unglamorous war: beetles, carp, buffelgrass — a logistics problem with a Latin name.",
            (
                "Early money is cheap. Late money is a forever occupation.",
                "A pet trade and a ballast tank will undo a decade of pulling weeds if you do not legislate the hose.",
                "Heroic restorations that skip maintenance are landscaping.",
            ),
            (
                ("buffel", "We pulled it for five years. A cattle fence and a spark undid the ridge. Maintenance is the project."),
                ("ballast", "The carp did not vote. The ship did. Regulate the ship."),
                ("early", "A $20k scrape now or a $20M occupation later. We always pick later."),
            ),
        ),
        (
            "Insect Drop",
            "A specialist cluster keeps returning to neonics, night lighting, and a food web that is quietly thinner.",
            (
                "If the pollinator is a service we rent from a truck, the landscape already failed.",
                "Lights that never dim are a habitat loss that does not look like a habitat loss.",
                "A pesticide that stays in the soil is not a one-season tool. It is a regime.",
            ),
            (
                ("bee-truck", "We import the pollination now. That sentence should end the debate about 'healthy fields'."),
                ("night-noon", "The parking lot is daylight at 2am. Moths are not a vibe. They are a night shift we fired."),
                ("neonic", "The seed is pre-poisoned. The label is a novella. The count is down."),
            ),
        ),
    ),
    "Farm Weather": faces(
        (
            "Crop Insurance",
            "Growers treat the policy as the real farm bill — a floor that also freezes bad habits in place.",
            (
                "A product that pays you to plant the same thing into a worse climate is not resilience. It is a habit subsidy.",
                "Premiums that hide the risk from the operating loan will keep producing surprises in July.",
                "If the actuarial table is political, the weather is still not.",
            ),
            (
                ("same-crop", "I insured corn again. The rain did not. That is the program."),
                ("july-surprise", "The loss was certain in May. The check is a winter story. Cash is a summer story."),
                ("table", "Do not 'improve' the table to make me plant into a desert. I can read a radar."),
            ),
        ),
        (
            "Drought",
            "This face is wells, fallow, and a feed bill that turns a cow into a liability.",
            (
                "A drought is a price in hay before it is a satellite image.",
                "Selling the herd is a one-way door. The genetics do not come back with the rain.",
                "Cities that buy the water and leave the dust are choosing a landscape.",
            ),
            (
                ("hay-bill", "The cows ate a truck of someone else's rain. That is drought accounting."),
                ("herd-sale", "I sold the genetics my grandfather kept. The rain can return. That cannot."),
                ("buy-the-water", "The suburb took the river. I took the dust. Very efficient allocation."),
            ),
        ),
        (
            "Flood Years",
            "The other tail: drowned fields, delayed planting, and a levee district that is a 1930s idea in a 2020s hydrograph.",
            (
                "Prevented planting is a real crop. It just does not photograph well.",
                "Levees that protect last decade's development starve this decade's floodplain. That is a choice.",
                "Tile and ditch that shunt water downstream faster are how a 'drainage success' becomes a neighbor's disaster.",
            ),
            (
                ("prevented", "I farmed a lake and a claim. The yield was a PDF."),
                ("levee-1936", "The district is a museum. The hydrograph is not."),
                ("tile", "We drained it in a day. The town downstream took our afternoon. That is hydrology, not luck."),
            ),
        ),
        (
            "Co-ops",
            "A hopeful cluster still treats the elevator, the rural electric, and the shared shop as the only scale a family farm can afford.",
            (
                "A co-op that remembers it is a member organization can bargain. A co-op that becomes a mini-Cargill cannot.",
                "Shared equipment is climate adaptation: you cannot all own the $800k planter.",
                "When the elevator is the only buyer, governance is the antitrust policy.",
            ),
            (
                ("member", "We voted out the CEO who thought we were a brand. We are a bin."),
                ("shared-planter", "Three families, one machine, a calendar. That is the only way the math closes."),
                ("only-buyer", "If they set the basis, they are a government. Elect them like one."),
            ),
        ),
    ),
    "Plastic Waste": faces(
        (
            "Packaging",
            "Shoppers meet the crisis as clamshells, chips bags, and a cucumber in armor.",
            (
                "If the product needs a second product to be held, the first product is overbuilt.",
                "Producer responsibility that is a fee into a black box is not design. It is an indulgence.",
                "Refill only scales if the store is built for it. A tote in a walk-in pantry is not a system.",
            ),
            (
                ("cucumber", "The cucumber had a jacket. I did not ask for a jacket. The jacket will outlive me."),
                ("epr-box", "They paid a fee and kept the clamshell. That is not responsibility. That is postage."),
                ("refill-aisle", "Put the bulk bins where the chips were. Then we can talk about my tote."),
            ),
        ),
        (
            "Recycling Myths",
            "This cluster is done with the chasing-arrows lie: most of it was always a thermal or a landfill story.",
            (
                "A symbol that means 'please feel fine' is marketing, not a material science.",
                "If China is not taking the bale, the bale was never a commodity. It was an export of confusion.",
                "Stop printing recyclable on a film that has never had a market. That is a fraud with a logo.",
            ),
            (
                ("arrow-lie", "I rinsed it for 20 years. Then I read the bale price. I was the product."),
                ("bale-port", "When the shipping stopped, the 'recycling' stopped. Honesty would have been cheaper.",),
                ("film", "The bag says store drop-off. The store has a locked bin. Cute."),
            ),
        ),
        (
            "Ocean Gyres",
            "A visible minority still wants the patch in the story — fishing gear, rivers, and a cleanup that cannot outrun the tap.",
            (
                "Nets and rivers beat straws. The straw was a mascot.",
                "Cleanup without a tap shutoff is a hobby with a catamaran.",
                "Waste pickers at river mouths are the actual infrastructure. Pay them like it.",
            ),
            (
                ("ghost-net", "The gear keeps fishing. The straw campaign does not. Fund the gear buyback."),
                ("tap", "I like the boom. I would like the factory less. Sequencing, please."),
                ("picker", "She is the system. The NGO is a camera. Put her on payroll."),
            ),
        ),
        (
            "Refill Shops",
            "A practical group is trying to make reuse boring: deposits, wash systems, and a SKU that comes home.",
            (
                "Deposits work because they put a price on the bottle that a human will chase.",
                "Reuse that depends on a lifestyle boutique will stay a boutique.",
                "If the brand will not take the container back, the brand is not in the circular anything.",
            ),
            (
                ("nickel", "Give me a deposit and a machine. I will be your logistics. I have been since 1982."),
                ("wash-hub", "The missing piece is a dishwasher for bottles, not another tote design."),
                ("take-back", "If you cannot reverse-logistics your own jar, do not lecture me about the ocean."),
            ),
        ),
    ),
    "Ocean Heat": faces(
        (
            "Coral",
            "Reef scientists treat bleaching as a clock: tourism, protein, and a shoreline that used to have a breakwater.",
            (
                "A reef that cooks in a hot week is not a mascot. It is a collapsed breakwater and a collapsed pantry.",
                "Restoration without cooling the water is gardening in an oven.",
                "Local sewage and overfishing still matter. They do not replace the temperature.",
            ),
            (
                ("hot-week", "We lost a garden in 14 days. The recovery brochure is a 20-year PDF."),
                ("breakwater", "The swell came in. The coral was not there. The hotel noticed."),
                ("oven", "I can plant fragments. I cannot plant a climate. Stop asking me to."),
            ),
        ),
        (
            "Fisheries",
            "Crews describe species walking poleward and quotas written for a map that has moved.",
            (
                "A quota on a fish that left is a regulation of a ghost.",
                "When the stock moves into another nation's water, the diplomacy is the fishery.",
                "Warm water plus overcapacity is how you get a boom, a bust, and a processing plant that outlives the fish.",
            ),
            (
                ("ghost-quota", "The paper still thinks they are here. The sonar does not."),
                ("line-moved", "They swam north. The treaty did not. That is now a navy problem."),
                ("boom-bust", "We built the plant for a decade that was a weather event. The debt remains."),
            ),
        ),
        (
            "Sea Level",
            "Coastal towns meet millimeters as insurance, buyouts, and a road that floods on a sunny day.",
            (
                "Nuisance flooding is the product. The storm is the commercial.",
                "Insurance retreat is managed retreat with better stationery.",
                "A seawall that saves the downtown and drowns the marsh is a choice about which public to keep.",
            ),
            (
                ("sunny-day", "The king tide took the road and we did not even get a named storm. That is the new baseline."),
                ("insurer-left", "They did not argue. They left. That is a climate model with a claims department."),
                ("wall-or-marsh", "We can keep the condos or the nursery. The army corps will not get both."),
            ),
        ),
        (
            "Marine Heatwaves",
            "This face is mass die-offs, cooked shellfish, and a 'blob' that is now a recurring season.",
            (
                "A heatwave in water does not look like weather to people inland. It looks like an empty pot.",
                "Early-warning for the surface is possible. Markets still pretend each blob is a surprise.",
                "Indigenous harvests that miss a year are not a cultural footnote. They are a food system.",
            ),
            (
                ("empty-pot", "The season closed itself. The regulator just typed it."),
                ("blob-again", "We named it once like it was a pet. It is a season. Plan."),
                ("harvest-gap", "The table missed a food that is not in the grocery. That is a heatwave too."),
            ),
        ),
    ),
    "Mining Boom": faces(
        (
            "Lithium",
            "The transition's hunger for batteries shows up as a brine pond, a mountain, and a county that has seen this movie.",
            (
                "A clean car with a dirty well is still a well. Count the water in the sticker price.",
                "If the ore is here, the consent has to be here. A national target is not a local yes.",
                "Recycling the pack is the second mine. Build it before you call the first one green.",
            ),
            (
                ("brine", "They need the water. We need the water. Only one of us is a slide in a climate deck."),
                ("local-yes", "I will take a mine I can tax and inspect. I will not take a target from a coast I cannot see."),
                ("second-mine", "When the pack is a feedstock, call me. Until then you are opening pits and adjectives."),
            ),
        ),
        (
            "Tribal Land",
            "Nations treat consultation that arrives after the PEA as the old pattern with a new mineral.",
            (
                "A sacred site does not become a sacrifice zone because the SUV is electric.",
                "FPIC that is a listening session is not consent.",
                "If the ore is on treaty land, the partner is a government, not a stakeholder to be managed.",
            ),
            (
                ("after-pea", "They consulted us in the PowerPoint. The drillers consulted the ground first."),
                ("not-stakeholder", "We are not a box on a NEPA form. We are the other sovereign."),
                ("same-pattern", "Uranium, coal, lithium. The adjective changes. The fence does not."),
            ),
        ),
        (
            "Tailings",
            "Engineers keep pointing at the dam: the unglamorous pile that outlives the commodity cycle.",
            (
                "A tailings failure is a forever chemical spill with a gravity assist.",
                "Bonding that assumes a cheerful bankruptcy is how towns inherit a lake of dust.",
                "Dry stack and liners cost money now. The other thing costs a watershed later.",
            ),
            (
                ("dam-eye", "I do not care about your ESG page. I care about the piezometers at 2am."),
                ("bond-joke", "The bond would plant some grass. It would not move the pile. That is the joke."),
                ("dry-stack", "Pay for the boring version. I would like the river to stay a river."),
            ),
        ),
        (
            "Critical Minerals",
            "Policy people want a domestic list, allies, and a reality check about concentrations that do not care about speeches.",
            (
                "A critical list without a permit clock is a wish list.",
                "Friend-shoring that still runs through one refinery is a sticker on the same chokepoint.",
                "Substitution and thrift are minerals policy. So is not putting a battery in things that do not need one.",
            ),
            (
                ("wish-list", "We named 50 minerals and permitted none. That is a brochure."),
                ("one-refinery", "The ore is diverse. The refinery is not. Guess which one is the strategy."),
                ("thrift", "Do we need a 9,000-pound commuter? The mineral does not think so."),
            ),
        ),
    ),
    "Conservation Land": faces(
        (
            "Public Access",
            "Hunters, hikers, and disabled visitors want the land actually usable — not a preserve you can only see from a highway pullout.",
            (
                "A park you cannot enter without a lottery and a high-clearance rig is a postcard, not a commons.",
                "Closing access to 'protect' a place while selling a scenic overlook to a resort is a class policy.",
                "If the public paid for it, the public needs a trailhead, a toilet, and a rule they can read.",
            ),
            (
                ("lottery", "I won the permit in year four. The land is public. The door is not."),
                ("overlook-club", "They gated the old road and opened a spa. Conservation, apparently."),
                ("toilet", "Access is a vault toilet and a sign. Without those you get a mess and a closure."),
            ),
        ),
        (
            "Working Forests",
            "This view wants mills, thins, and a rural wage treated as part of the habitat, not as the villain in a sticker campaign.",
            (
                "A forest that cannot be thinned will choose fire as the contractor.",
                "Exporting the cut and importing the lumber is how you lose both the mill and the argument.",
                "Owls versus jobs was a bad frame. Habitat plus a mill is a harder, better one.",
            ),
            (
                ("thin-or-burn", "We studied it until it burned. The study was very careful."),
                ("mill-gone", "The logs go to a port. The town goes to a museum. That is not ecology. That is a trade policy."),
                ("both", "I can hold a spotted owl and a paycheck. The bumper stickers cannot."),
            ),
        ),
        (
            "Easements",
            "Landowners describe conservation easements as a tool that can keep a ranch intact — or as a tax product with a view.",
            (
                "An easement that pays a billionaire to keep a view is not the same as one that keeps a family on a hardscrabble bench.",
                "Perpetuity is a long time to get the language wrong. Write the grazing and fire clauses like adults.",
                "If the NGO will not show up for the fence, they bought a painting, not a working landscape.",
            ),
            (
                ("view-tax", "He deducted a ridgeline. I deducted a cow. Only one of us needed the program."),
                ("perpetuity", "Put fire and grazing in the deed. Pretty is not a management plan."),
                ("fence-day", "They came for the photo. I still need a partner for the wire."),
            ),
        ),
        (
            "Firebreaks",
            "Communities at the wildland edge want cuts, goats, and a defensible space that is not a brochure on a fridge.",
            (
                "A home hardening rebate without a break on the ridge is a lottery ticket.",
                "Letting the fuel accumulate because the lawsuit was easier than the cut is how you get a plume.",
                "Goats and crews are cheaper than a subdivision-wide rebuild. The budget does not act like it.",
            ),
            (
                ("ridge-cut", "Harden my vents. Also cut the ridge. I cannot foam a hillside."),
                ("lawsuit-fuel", "They did not thin because someone might see a stump. We all saw the plume instead."),
                ("goat-bill", "The goats were a joke until the invoice for the houses landed. Hire the joke."),
            ),
        ),
    ),
}
