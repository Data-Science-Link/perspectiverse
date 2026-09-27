# Similar Products and Differentiation

Perspectiverse sits in a crowded neighborhood of tools that all claim to "understand what people are saying online." Most of those tools are built for a different job: protect a brand, brief a comms team, or run a structured debate. This note maps that landscape and says, specifically, what this project does that they do not.

The one-line difference: **Perspectiverse is an unsupervised public observatory of a week's conversation, rendered so scale and multiplicity are visible at a glance.** It is not a mention inbox, not a sentiment score, and not a poll.

## What Perspectiverse is optimizing for

The architecture canvas calls the product an "empathy machine." That is not branding. It is the product constraint.

Social feeds and most dashboards hide two facts that matter for civic reading:

1. **Scale is distorted.** Engagement algorithms and crisis alerts treat a loud cluster as if it were the week's largest object. A manufactured culture-war spike can occupy the same visual real estate as housing costs.
2. **Topics are flattened to a line.** Sentiment tools collapse a topic to positive / negative / neutral. News-literacy tools often collapse it to left / right. Real conversations have more than two faces.

Perspectiverse answers those with two visual rules:

- **Gravity for volume.** The largest topic is the sun. The next nine orbit by volume. Planet size is share of the kept conversation, not virtue and not virality.
- **Six faces, always.** Every planet is a cube. Each face is a dominant perspective inside that topic. Spike length is that face's share. A lopsided cube is a lopsided conversation.

A third rule is easy to miss if you only look at the 3D scene:

- **The week chooses the topics.** The pipeline does not start from a brand, a keyword, a hashtag, or a policy prompt. It samples a window of public English posts, clusters them, and keeps the ten largest neighborhoods. You find out what the week was about. You do not tell the software what to look for.

The current live source is Bluesky. The sidebar is explicit that this is internet discourse, not a sample of humanity, and that a one-sentence face label washes out dissent inside that cluster. Those limits are part of the product, not footnotes.

## The landscape, in one table

| Family | Typical job | Typical starting question | What you see | Who it is for |
| --- | --- | --- | --- | --- |
| Social media monitoring | Catch and answer mentions | "Who tagged us in the last hour?" | Inbox, alerts, response queues | Community managers, support |
| Social listening | Find themes around a query | "What are people saying about our category?" | Sentiment charts, word clouds, topic lists | Marketing, insights |
| Brand / reputation monitoring | Protect a named entity everywhere | "Where did our name appear today?" | Mention streams across news, social, reviews, AI answers | PR, brand, executives |
| Media monitoring | Track earned coverage | "Which outlets covered the announcement?" | Clip books, share of voice, AVE-style reports | PR, comms |
| Crisis and risk intelligence | Detect events that need a response now | "Is something breaking that will hit us?" | Real-time alerts, geolocation, escalation | Security, comms, government |
| Narrative / influence intelligence | See how a story moves through networks | "Who is amplifying this, and is it coordinated?" | Account graphs, community maps, momentum scores | Agencies, researchers, intel |
| Audience intelligence | Profile the people talking | "Who is this community?" | Demographics, affinities, segments | Marketing, political targeting |
| Civic deliberation | Help a group think together | "What do *these participants* agree on?" | Opinion maps, pro/con trees, consensus statements | Governments, classrooms, communities |
| Media-bias / news literacy | Compare how outlets frame a story | "How does left vs right cover this event?" | Bias bars, blindspot feeds, side-by-side headlines | Readers, classrooms |
| Media-ecosystem research | Study the news system itself | "Which outlets ran this frame?" | Collection comparisons, event databases | Academics, NGOs |
| Misinformation / claim tracking | Follow a rumor | "How did this claim spread?" | Diffusion graphs, fact-check overlays | Researchers, platforms |
| Search-attention tools | Measure curiosity, not argument | "Are people searching for this?" | Interest over time | Strategy, journalism |
| Researcher topic maps | Explore a corpus you already have | "What clusters exist in *this* dataset?" | Embedding maps, word networks | Data scientists, CSS labs |
| Polling and CX | Ask a designed question | "What % of adults support X?" | Crosstabs, NPS, Likert scores | Researchers, product, politics |
| **Perspectiverse** | Read the week's public conversation as a sky | "What were people actually talking about, and from how many angles?" | Solar system of 10 topics × 6 perspectives, then the posts | Anyone who wants to see the week, not manage a brand |

The rest of this document unpacks each family and the exact gap.

## 1. Social media monitoring

**Examples:** Hootsuite / Perch, Sprout Social, Sprinklr's engagement inbox, native tools (TweetDeck-style columns, platform search).

**What they do.** Monitoring is operational and reactive. You track @mentions, tags, keywords, and customer questions as they arrive, then reply or escalate. Industry write-ups in 2026 still draw the same line: monitoring answers "what is being said *to us* right now?"

**What they optimize.** Response time, ticket volume, SLA, saved replies. The unit of work is a mention.

**How Perspectiverse differs.** There is no inbox, no keyword watchlist, and no reply workflow. A post that never names a brand can still become part of a planet if enough neighbors say the same kind of thing. Perspectiverse is not trying to help anyone answer the internet. It is trying to show what the internet spent the week on.

If you need to know that a customer just complained on Bluesky, use a monitor. If you need to know whether "customer complaints about airlines" was even a top-ten object this week, use this.

## 2. Social listening

**Examples:** Brandwatch, Talkwalker (now the listening engine behind Hootsuite Lumen), Meltwater social, Pulsar TRAC, Sprinklr Consumer Intelligence, YouScan, Brand24.

**What they do.** Listening is the strategic sibling of monitoring. You still start with a query — a brand, a competitor set, a category, a campaign hashtag — then analyze volume, sentiment, emotions, share of voice, and emerging themes over weeks or months. Enterprise platforms add image recognition, multilingual coverage, and natural-language "ask the data" copilots.

**What they optimize.** A comms or insights team that already knows *what* it cares about and wants trends, benchmarks, and slides. The unit of work is a Boolean (or AI-rewritten) query and a dashboard.

**How Perspectiverse differs.**

- **Query-shaped vs week-shaped.** Listening tools are excellent at "everything about Brand X." They are structurally bad at "what mattered this week if I do not name a brand." If housing costs dominate the sample and your query was "AI regulation," housing never appears. Perspectiverse inverts that: unsupervised clustering, then keep the ten largest remaining neighborhoods. Topic -1 (noise) is dropped from the percentages on purpose.
- **Sentiment line vs six faces.** Listening sentiment is usually positive / negative / neutral, sometimes with emotion tags. That is the binary the architecture canvas is written against. A planet here must show six perspectives. "Financial," "ethical," and "skeptical" can coexist on one cube. A 50% spike is visible as geometry, not a footnote under a pie chart.
- **Analyst UI vs public observatory.** Listening UIs assume a trained user who will build queries, save dashboards, and export CSVs. Perspectiverse assumes a visitor who will drag the sky, click a planet, and read posts. The 3D metaphor is the interface, not a novelty skin on a table.

Listening is the category people reach for first, and it is the one this project is most often confused with. The shared ingredient is "cluster social posts and label them." The jobs are opposite: listening *narrows* to a commercial object; Perspectiverse *opens* to the week's objects.

## 3. Brand monitoring and reputation intelligence

**Examples:** Mention, Brand24, Fullintel, Meltwater, Onclusive, and the newer "AI search / GEO" monitors that track how a brand appears in ChatGPT-style answers.

**What they do.** Brand monitoring is the superset PR teams buy. It follows a named entity across social, news, broadcast, reviews, forums, podcasts, and increasingly AI-generated answers. The outputs are mention streams, share of voice, executive tracking, and crisis flags.

**What they optimize.** Reputation risk for an organization that already knows its name, its execs, and its competitors.

**How Perspectiverse differs.** There is no entity graph. The pipeline does not resolve "Apple" vs fruit. It does not score brand health. A company can appear inside a planet if people talked about it a lot, but the product is not *for* that company. The value is the opposite of brand-centrism: you see topics that have no brand attached, which is most of public life.

## 4. Media monitoring (earned media)

**Examples:** Cision, Meltwater's media products, Onclusive, NewsWhip (predictive news attention), classic clip services.

**What they do.** Track editorial coverage — news, trade press, broadcast — and report who published what, with what tone, and with what estimated reach.

**How Perspectiverse differs.** The corpus is public social posts, not newsrooms. Editorial attention and public attention diverge constantly. A story can lead every homepage and still be a small planet, or the reverse. Perspectiverse is closer to "what people said" than "what outlets ran." For the outlet layer, see Ground News, Media Cloud, and GDELT below.

## 5. Crisis, risk, and social intelligence

**Examples:** Dataminr, Recorded Future, Primer Command, Pulsar's crisis / narrative-velocity modules.

**What they do.** These products sell *time*. They watch firehoses for breaking events, threats, deepfakes, and coordinated bursts, then page an analyst. The 2026 enterprise guides split the market into volume-led listening (Brandwatch, Meltwater), audience-led intelligence (Pulsar, Audiense), and risk-led alerting (Dataminr).

**How Perspectiverse differs.** The pipeline runs once a day on a 7-day window and writes a static `data.json`. That is a feature. A daily gravitational map is meant to be semantically stable, cheap, and readable. It is a terrible paging system. If something is on fire at 2 a.m., this sky will not tell you until the next snapshot, and even then only if the cluster was large enough to become a planet.

## 6. Narrative intelligence and influence mapping

**Examples:** Graphika, Primer's narrative monitoring, Pulsar Narratives AI.

**What they do.** They model *propagation*: which communities, accounts, and amplifiers move a story, whether the activity looks organic, and how fast a narrative is accelerating. Graphika's own positioning is explicit: traditional tools count mentions and sentiment; Graphika maps relationships between accounts and communities.

**How Perspectiverse differs.** Clustering here is on *post text*, not on who follows whom. A face is a neighborhood of similar language, not a community of similar accounts. You will not see coordination, bots, or information brokers. You will see that, inside "housing," one spike is "rents vs wages" and another is "zoning." Those are complementary pictures. Influence maps answer "who is moving this." Perspectiverse answers "what the moving looks like when you ignore who is speaking and listen to the words."

## 7. Audience intelligence

**Examples:** Audiense, Pulsar CORE, platform ads managers.

**What they do.** Profile the people in a conversation: demographics, interests, media diets, lookalike segments.

**How Perspectiverse differs.** The observatory does not attempt to say who is talking. Bluesky handles appear only as authors of representative posts. There is no psychographic overlay, on purpose. Audience tools are useful and easy to misuse. This project is about the shape of the talk, not the marketable identity of the talkers.

## 8. Civic deliberation and structured opinion mapping

This is the closest *philosophical* neighborhood, and the most important contrast after social listening.

### Pol.is

Pol.is is an open-source system for gathering what a large group thinks *in their own words*. Participants write statements. Others vote agree / disagree / pass. There is no reply thread, which cuts trolling. Machine learning projects voters into a 2D opinion landscape and finds 2–5 opinion groups. Reports highlight comments that bridge groups (rough consensus) as well as comments that define a minority. It has been used in civic processes such as vTaiwan.

Pol.is maps **people who opted into a conversation about a framed issue.** Perspectiverse maps **posts that already existed**, about whatever the week produced, from people who were not asked to vote.

That difference is the whole product:

| | Pol.is | Perspectiverse |
| --- | --- | --- |
| Input | Statements + votes, inside a hosted conversation | Unstructured public posts, sampled after the fact |
| Unit clustered | Participants (by voting pattern) | Posts (by text) |
| Question | "Where do *we* agree and split on this issue?" | "What issues existed this week, and what faces did each have?" |
| Participation | Required | None |
| Consensus | A first-class output | Not computed |
| Scale correction | Not the point | The point of the solar system |

Pol.is is a better tool for writing a policy that a specific public can live with. Perspectiverse is a better tool for noticing that the issue you care about was not, this week, one of the ten largest objects in the sample — or that it was, and had six faces you were not reading.

### Consider.it

Consider.it is a deliberation forum: a slider for overall stance, plus a shared pro/con list. It visualizes what a community thinks *and why*. It was designed at the University of Washington for civil large-group dialogue.

Again: participants, a proposal, structured input. Perspectiverse has no proposal and no slider. It will surface perspectives that nobody convened.

### Kialo and DebateGraph

Kialo is a collaborative argument tree (pro/con under claims). DebateGraph is a shared ontology of issues, positions, and arguments, used by newsrooms and governments. Both are **authored maps**. Quality depends on people showing up and placing nodes. They are superb for teaching reasoning and for holding a complex brief in one picture.

Perspectiverse is **inferred**, not authored. Nobody draws the six faces. k-means does, then an LLM writes a two-word title and a sentence. That is faster and more honest about "what was said a lot," and worse at "what is the best argument." A Kialo con that is rare but decisive will never grow a long spike here. Volume is not merit. The sidebar says so.

### Issue and controversy mapping

Academic controversy-mapping (Issue Crawler, Govcom.org, and the "mapping controversies" tradition) traces actors, documents, and linkages around a public issue. Those maps are research instruments. Perspectiverse is a public sky with a fixed 10×6 schema. It will not replace a controversy map. It might tell you which controversy was large enough this week to deserve one.

## 9. Media-bias and news-literacy products

**Examples:** Ground News, AllSides, Ad Fontes Media, Media Bias/Fact Check.

**What they do.** Ground News clusters outlet articles about the same *event* and shows a bias bar averaged from AllSides, Ad Fontes, and Media Bias/Fact Check. Blindspot feeds highlight stories one side of the spectrum barely covers. AllSides rates *publications* with multipartisan editorial reviews and blind surveys. The reader is meant to escape a single-outlet frame.

**How Perspectiverse differs.** Those products map **newsrooms**. This one maps **posts**. Left-vs-right is a one-dimensional overlay on professional media. A Perspectiverse cube is not a political spectrum. A health planet can have faces for cost, trust in institutions, personal protocol, and skepticism without assigning them a party. Complementary, not competing: Ground News tells you how the press split; Perspectiverse tells you how a social sample split, including topics the press ignored.

## 10. Media-ecosystem research

**Examples:** [Media Cloud](https://mediacloud.org/) (open research on how selected collections of outlets cover terms and stories), [GDELT](https://gdeltproject.org/) (global news, broadcast, and web events, themes, and tone, supported by Google Jigsaw).

**What they do.** These are corpora and query surfaces for people who want to compute on the news system: geographic coverage, source sets, tone over time, knowledge graphs of people and organizations.

**How Perspectiverse differs.** Different corpus (social vs news), different audience (visitor vs researcher), different output (one daily 3D snapshot vs APIs and dashboards). If you need "how Iranian state media and US cable covered the same week," use GDELT or Media Cloud. If you need "what this Bluesky sample argued about," use this.

## 11. Misinformation and claim diffusion

**Examples:** Hoaxy, Botometer-class tools, NewsGuard-style reliability layers, platform integrity dashboards.

**What they do.** Trace how a URL or claim moves, and sometimes whether amplifiers look automated.

**How Perspectiverse differs.** No claim graph, no fact-check overlay, no bot score. A viral falsehood can become a long spike if many posts cluster there. The product will not tell you it is false. Treating volume as truth is the failure mode the UI is written to resist ("a long spike is not louder because it is truer").

## 12. Search attention

**Examples:** Google Trends, Exploding Topics, and "what is trending" surfaces on the platforms themselves.

**What they do.** Measure *curiosity* — queries typed into a search box — or *platform-defined* trends. Google Trends is a normalized interest index, not a count of arguments.

**How Perspectiverse differs.** Searching for a term and arguing about it are different behaviors. Trends will not give you six faces. Platform "trending" is also a poor picture of scale: it is whatever the ranking system chose to boost. The solar system is a counter-ranking. It is still a sample, still biased, but the ranking rule is "largest clusters in this extract," not "most engaging."

## 13. Researcher topic maps and text networks

**Examples:** [Nomic Atlas](https://atlas.nomic.ai/) (embedding maps with hierarchical topic labels), [InfraNodus](https://infranodus.com/) (words as a network; topics as communities; structural gaps), [Communalytic](https://communalytic.org/) (computational social science, including 3D views of a collected corpus), BERTopic's own visualizations, pyLDAvis, Voyant, Overview, TensorBoard's embedding projector.

**What they do.** Take a corpus *you bring* and let you wander: point clouds, word graphs, zoomable topic hierarchies. Nomic in particular is close on the NLP: embed, cluster, auto-label with an LLM. InfraNodus is close on the "see the structure of a discourse" goal, but the metaphor is a concept graph, and the user is usually a researcher or writer working a specific text.

**How Perspectiverse differs.**

- **Fixed civic schema vs open explorer.** 10 planets × 6 faces is a deliberate reduction. Atlas will happily show you 200 clusters at three depths. That is better for research. It is worse for a public that needs one sky they can finish.
- **Metaphor with a thesis.** An embedding plot does not argue that scale is distorted or that binary sentiment is a lie. The solar system and the spiky cube *are* those arguments. Geometry is the editorial.
- **Hosted observatory vs BYO corpus.** You do not upload a CSV to read Perspectiverse. The daily job *is* the corpus. That makes it a place, not a lab instrument.
- **Drill-down to posts in public language.** The sidebar is a reading room: title, sentence, then the actual posts sorted by likes. Many research UIs stop at keywords or coordinates.

If you are a computational social scientist who already has 100k posts and a question, Atlas or Communalytic will go further. If you want the public to walk into one URL and feel the week's proportions, those tools are the wrong shape.

## 14. Polling, surveys, and customer-experience scores

**Examples:** Gallup, Pew, YouGov; Qualtrics, Medallia; NPS and CSAT dashboards.

**What they do.** Ask a designed question of a designed sample (or of your customers) and report a number with a margin of error — or, in CX, a score tied to a journey.

**How Perspectiverse differs.** It is not a poll. The welcome panel says so. Bluesky is younger, more Western, more tech-centric than a country. There is no weighting, no likely-voter model, no "52% support." Treating a long spike as public opinion is a category error. The value is the opposite of a topline number: you see *structure* (what clustered, how lopsided) in a population you must not over-generalize.

Use a poll when you need to know what a defined public would answer. Use this when you need to know what a defined feed spent its breath on.

## 15. Adjacent tools that are easy to mix in

A few more products show up in the same browser history and are worth naming so they are not mistaken for the same job.

- **Social publishing and community management** (Buffer, Later, native composers). These schedule outbound posts. No overlap except that they also "do social."
- **News treemaps** such as [Newsmap](https://newsmap.jp/). Google News headlines as a treemap: size is coverage volume. Close on "scale as area," but the atoms are articles, not perspectives, and there is no six-face drill-down.
- **Conversation intelligence** (Gong, Chorus). These transcribe *sales calls*. Corporate, private, not public discourse.
- **Review and app-store intelligence.** Brand-adjacent, product-scoped.
- **3D solar-system explainer sites.** Same rendering trick, different data. Perspectiverse borrows the physics as a literacy device, not as astronomy.

## Where the value actually is

The useful question is not "is this better than Brandwatch?" It is "what can a person do here that they cannot do in those products without a research team?"

### 1. See the week's objects without a query

Almost every commercial tool requires you to already know the noun. That sounds small. It decides the worldview. Query-shaped software can only surprise you *inside* the frame you bought. Week-shaped software can tell you the frame was wrong: the thing you have been arguing about was a small moon; the thing you have not been reading was the sun.

That is the civic version of what listening teams call "unknown unknowns," without a brand subscription or a Boolean specialist.

### 2. Feel proportion

Dashboards can print "12% of posts." Most readers do not feel 12%. They feel whatever the feed last showed them in full screen. A gravitational layout makes the 12% planet smaller than the 31% sun, every time, without a legend. The architecture canvas's housing-costs-vs-culture-war example is the intended use. Fringe outrage can still be a planet. It cannot be the same size as the thing that actually ate the sample.

### 3. Force more than two sides

Binary UIs (sentiment, left/right, pro/con) are easy to ship and easy to weaponize. The cube is a constraint: the pipeline *must* cut six faces. Some will be messy. Some will be near-duplicates. The point is the refusal to stop at "people are mad." A visitor who clicks one planet is not allowed to leave with a single story about that topic.

Kialo can also show many sides, but only the sides someone typed into Kialo. Perspectiverse shows the sides that showed up in the wild, weighted by how many posts landed there.

### 4. Keep the chain back to speech

A face is not an oracle. It is a title, a sentence, and a stack of real posts. The product is built so a skeptical reader can disagree with the label by reading the evidence. Listening tools often stop at the theme name. Polls never show you the respondents. This is closer to a primary source room with a map on the wall.

### 5. Stay cheap, inspectable, and slow on purpose

Enterprise listening is a budget line. Pol.is is a process you have to run. Atlas is a platform you upload to. Perspectiverse is a static site plus a daily job that can run on GitHub Actions for cents of LLM calls (or free via Ollama). The 7-day window and the once-a-day refresh are how it avoids both semantic jitter and a cloud bill. "Live mapping" here means "the sky updates every morning," not "the graph twitches with every post."

That cost model is part of the value. A public observatory that only a university or a holding company can afford is not public.

### 6. Tell the truth about the sample

Most commercial pages imply completeness ("30+ channels," "billions of conversations"). This project's UI leads with what it is not: not humanity, not a poll, not a complete account of dissent inside a cluster, not a count that includes the noise bucket. Honesty is a feature because the metaphor is powerful enough to be misread as a god's-eye view.

## What this does *not* add

A differentiation note that only lists wins is a brochure. These are the jobs you should take elsewhere.

- **Do not use it for customer response, brand health, or crisis SLA.** No alerts, no entity resolution, no multi-channel firehose.
- **Do not use it as public opinion.** Bluesky English, 7 days, sampled, outliers dropped. Demographic bias is structural.
- **Do not use it to find the best argument.** Volume ranks faces. A rare, careful comment loses to a common one.
- **Do not use it to detect coordination, bots, or influence operations.** No social graph.
- **Do not use it to fact-check.** No claim layer.
- **Do not use it as a news-bias trainer.** It does not rate outlets.
- **Do not expect real-time or full-platform coverage.** One source today, one snapshot a day, default live sample still small (200 in the example config; 10k is the commented production target).
- **Do not treat the six labels as complete.** The LLM sees representative posts, not every post. Minority views inside a face disappear into one sentence. That is documented in the architecture canvas as "margin flattening."

## A short chooser

- You manage a brand and need mentions, sentiment, and share of voice → **listening / brand monitoring**.
- You need to reply before lunch → **monitoring**.
- Something may be breaking in the next hour → **Dataminr-class risk**.
- You need to know which accounts or communities are pushing a story → **Graphika / narrative intelligence**.
- You are writing policy with a convened public → **Pol.is or Consider.it**.
- You are teaching argument → **Kialo**.
- You want to see how the *press* split on an event → **Ground News / AllSides**.
- You are studying news collections or global events → **Media Cloud / GDELT**.
- You already have a corpus and a research question → **Nomic Atlas, InfraNodus, Communalytic, BERTopic**.
- You need a number about a defined population → **a poll**.
- You want to stand in front of this week's public talk, see what was large, and turn a topic until you have read six ways people stood inside it → **this**.

## Sources

Industry definitions of monitoring vs listening vs brand vs media monitoring are consistent across vendor explainers from [Brand24](https://brand24.com/blog/social-listening-vs-social-monitoring/), [Onclusive](https://onclusive.com/resources/blog/social-media-monitoring-vs-social-listening/), [Hootsuite](https://blog.hootsuite.com/social-media-monitoring-tools/), [Sprinklr](https://www.sprinklr.com/blog/social-media-monitoring/), and [Fullintel](https://fullintel.com/blog/what-is-brand-monitoring-and-why-its-critical-for-modern-brands/). Enterprise splits (volume / audience / risk) follow 2026 buyer guides such as [Pulsar's](https://www.pulsarplatform.com/compare/best-social-media-intelligence-tools-2026). Narrative-intelligence positioning is from [Graphika](https://www.graphika.com/how-it-works) and [Primer](https://www.primer.ai/solutions/narrative-monitoring-and-analysis). Civic tools: [Pol.is](https://pol.is/home), the [Polis methods paper](https://www.e-revistes.uji.es/index.php/recerca/article/view/5516/6558), [Consider.it](https://eu.consider.it/tour), [Kialo](https://en.wikipedia.org/wiki/Kialo), [DebateGraph](https://debategraph.org/). News literacy: [Ground News](https://ground.news/about), [AllSides methods](https://www.allsides.com/about/media-bias-rating-methods). Research corpora and maps: [GDELT](https://gdeltproject.org/), [Nomic Atlas](https://docs.nomic.ai/atlas/datasets/data-maps), [InfraNodus](https://infranodus.com/), [Communalytic](https://communalytic.org/).

Product behavior described here matches this repo: 7-day window, 10 planets, 6 faces, static `public/data.json`, Bluesky extract, and the honesty copy in `src/components/Sidebar.jsx`. See also [Project Architecture: Discourse Universe](Project%20Architecture_%20Discourse%20Universe.md).
