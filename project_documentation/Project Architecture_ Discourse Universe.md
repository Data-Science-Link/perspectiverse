# **Project Architecture: Discourse Universe**

**A 3D Gravitational Visualization of Public Sentiment**

The sections below are the original canvas. What ships is a daily Bluesky job, local MiniLM embeddings, up to ten planets, and one to six opaque spikes on a cube. Empty cube sides are dashed. The living description is [ROADMAP.md](../ROADMAP.md) and [pipeline/README.md](../pipeline/README.md).

## **1\. Executive Summary & Concept**

**Discourse Universe** is a 3D data visualization tool that maps abstract, chaotic human discourse from social media into an intuitive, physical solar system.

* **The Planets (Macro-View):** The top 10 most discussed topics are represented as planets orbiting a central sun (the \#1 most discussed topic). Planet size correlates to the volume of mentions.  
* **The Cubes (Micro-View):** Instead of spheres, each planet is a 3D cube. One to six faces carry the perspectives that are actually different, summarized by an LLM when a key is present. A cube side with no perspective stays the planet color with dashes.

## **2\. Motivation & Societal Value**

While standard sentiment dashboards (bar charts, line graphs) are built for data analysts, Discourse Universe acts as an "empathy machine" built for the general public. Social listening, brand monitoring, polling, and civic deliberation tools sit in the same neighborhood and optimize for different jobs; the landscape and the gaps are in [Similar Products and Differentiation](Similar%20Products%20and%20Differentiation.md). It solves two major issues with modern media consumption:

1. **Correcting the Distortion of Scale:** Social algorithms often make fringe outrage seem like the most important issue in the world. By utilizing a gravitational physics model, users intuitively grasp scale. A manufactured culture-war asteroid is visually dwarfed by a massive gas-giant representing housing costs.  
2. **Forcing Nuance:** A planet shows the stances that are actually different, from one face to six. It does not invent a pro and a con. Empty cube sides stay dashed so a missing view is visible.

## **3\. System Architecture: The 7-Day Rolling Window**

To prevent semantic drift (where topics change so fast the visualization becomes chaotic) and to eliminate massive API/compute costs, the system uses a **Daily Refresh with a 7-Day Rolling Window**.

* **Pacing:** The backend pipeline runs only once every 24 hours.  
* **Data Scope:** It processes the last 168 hours (7 days) of data, providing deep semantic stability.  
* **Output:** It generates a single, static data.json file that dictates the entire state of the 3D solar system for the next 24 hours.

## **4\. The AI / NLP Pipeline (Two-Phase Processing)**

The core challenge is categorizing 100,000+ posts into clean topics and labeling them without spending hundreds of dollars on LLM tokens. The solution is separating the sorting from the labeling.

### **Phase 1: Traditional NLP (The Sorter)**

* **Technology that ships:** local MiniLM embeddings (fastembed) on the daily job. Pytest uses TF-IDF and k-means. BERTopic is optional locally and is not the scheduled path. HDBSCAN is not installed.
* **Why not force ten buckets?** The job finds tight groups, drops a loose one, and publishes at most ten. Posts that fit none of them stay Topic −1 and out of the percentages.
* **The Workflow:** Embed the claims, keep groups that are large and cohesive, rank them by distinct authors, then split a planet only when another face is large and far from the ones already kept.

### **Phase 2: The LLM (The Explainer)**

* **Technology:** GPT-4o-mini (or Anthropic Haiku) via API.  
* **The Workflow:** We take the top 50 most representative posts from each of the 6 faces across all 10 planets (60 groups total). We prompt the LLM: *"Read these 50 posts. Output a JSON object with a 2-word title and a 1-sentence summary of the core perspective."*  
* **Efficiency:** By only passing the most representative posts of the 60 pre-sorted clusters, we only make 60 small LLM calls per day.

## **5\. Frontend & 3D Visualization**

* **Technology:** React, Three.js (via React Three Fiber).  
* **Behavior:** The frontend is entirely static. It fetches data.json on load.  
* **Interactivity:** Users can watch the orbits, hover over planets for macro-stats, and click a planet to lock the camera. Once locked, the user can click-and-drag to rotate the cube and read the 6 LLM-generated summaries mapped to the faces as textures. Filters (e.g., "Politics", "Sports") instantly reload the 3D scene using pre-calculated category data from the JSON file.

## **6\. Hosting & Cost Breakdown**

Because the heavy lifting is completely isolated to a daily background job, the hosting architecture is practically free.

| Component | Tech Stack | Estimated Monthly Cost |
| :---- | :---- | :---- |
| **Data Ingestion** | Reddit API / Bluesky AT Protocol | $0 (Free tiers) |
| **Pipeline Runner** | GitHub Actions (Cron Job) | $0 (Free tier) |
| **LLM Summarization** | OpenAI (GPT-4o-mini) | \~$0.20 ($0.003/day) |
| **Frontend Hosting** | Vercel / Netlify | $0 (Static hosting) |
| **Total** |  | **Under $1.00 / month** |

## **7\. Critiques & Limitations**

To maintain analytical integrity, the project must acknowledge the following blind spots:

* **Demographic Bias:** Reddit and Bluesky do not represent the global population. They skew younger, more male (Reddit), and highly Western/tech-centric. This visualizes the *Internet's* discourse, not humanity's.  
* **Margin Flattening:** When an LLM summarizes a cluster of 500 posts into one sentence, it naturally prioritizes the loudest, most consensus-driven voice in that group. Highly nuanced or minority opinions within that sub-cluster will be washed out.

## **8. Development Roadmap**

Stages 1–4 below were the Cursor MVP. What shipped since: Bluesky extract, MiniLM on the daily job, up to 10 planets with 1–6 faces, a 10,000-claim window, a daily Actions job, and a static React Three Fiber observatory. Face textures and Reddit ingestion are not in the current code.

The living roadmap — including planet-level debate, an LLM clerk, retaining posts, custom brand universes, a Google plugin, historical solar systems, and what those cost to keep alive — is **[ROADMAP.md](../ROADMAP.md)**. Architecture for the newer surfaces:

* [Planet Engagement Architecture](Planet%20Engagement%20Architecture.md) — talk to a planet or a face without breaking the daily/static split
* [Custom Universe and Archive Architecture](Custom%20Universe%20and%20Archive%20Architecture.md) — retain more than twelve posts; generate a solar system from a brand or a highlighted sentence
* [Historical Solar Systems and Topic Continuity](Historical%20Solar%20Systems%20and%20Topic%20Continuity.md) — rewind a day, trend a topic, and align names that drift across independent cluster runs

MVP stages (historical):

* **Stage 1: Data Ingestion:** Python scripts to authenticate with Reddit/Bluesky APIs, pull 7 days of data, clean text (regex/spam filtering), and store in SQLite. *(Bluesky path shipped; Reddit not started.)*
* **Stage 2: The NLP Engine:** MiniLM on the daily job; TF-IDF in tests. Up to ten topics, one to six faces.
* **Stage 3: LLM Integration & Automation:** JSON labels from Ollama or a mini model; GitHub Actions daily; fallback titles when neither is present.
* **Stage 4: 3D Web Frontend:** React Three Fiber observatory, inspect mode, mobile drill-down, representative posts in the sidebar.

## **9. Cost model (honest)**

The 7-day window and the once-a-day job exist so the public solar system stays under a dollar. That holds only while we throw the sample away and publish a snapshot.

| Mode | What we keep | Typical monthly maintain |
| --- | --- | --- |
| **Today** | `data.json` on `data-snapshot` + `live_corpus.db` on R2 | **about $1**, plus Jev per fetched post |
| **Thicker snapshot** | More representative posts, terms, briefing cards | still **~$0–$1** |
| **Dated solar systems + matcher** | Keep each day's JSON; align topics after the fact | still **~$0–$1** if files stay static |
| **Planet LLM clerk** | Quote packs + a gated model | **$5–$20** box, then **tokens** ($0 if Ollama; hundreds if public and ungated) |
| **Custom universes / plugin** | Query drains or a short firehose window + on-demand cluster | **$20–$80** lean; more if we chat on every solar system |
| **Unbounded firehose** | Years of raw posts | storage on the order of **$20–$50 per retained year** plus ingest and legal review |

Do not put an API key in the Pages bundle. Do not generate a new universe in the visitor's browser. Those two choices are how this cost table stays true.