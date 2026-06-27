# **Project Architecture: Discourse Universe**

**A 3D Gravitational Visualization of Public Sentiment**

## **1\. Executive Summary & Concept**

**Discourse Universe** is a 3D data visualization tool that maps abstract, chaotic human discourse from social media into an intuitive, physical solar system.

* **The Planets (Macro-View):** The top 10 most discussed topics are represented as planets orbiting a central sun (the \#1 most discussed topic). Planet size correlates to the volume of mentions.  
* **The Cubes (Micro-View):** Instead of spheres, each planet is a 3D cube. The 6 faces of the cube represent the 6 dominant perspectives, themes, or sentiments driving that specific topic, summarized into human-readable labels by an LLM.

## **2\. Motivation & Societal Value**

While standard sentiment dashboards (bar charts, line graphs) are built for data analysts, Discourse Universe acts as an "empathy machine" built for the general public. It solves two major issues with modern media consumption:

1. **Correcting the Distortion of Scale:** Social algorithms often make fringe outrage seem like the most important issue in the world. By utilizing a gravitational physics model, users intuitively grasp scale. A manufactured culture-war asteroid is visually dwarfed by a massive gas-giant representing housing costs.  
2. **Forcing Nuance:** By requiring every topic to be viewed through 6 distinct faces (e.g., Financial, Ethical, Skeptical), the UI forces users to confront the reality that issues are multi-dimensional, breaking binary "For vs. Against" echo chambers.

## **3\. System Architecture: The 7-Day Rolling Window**

To prevent semantic drift (where topics change so fast the visualization becomes chaotic) and to eliminate massive API/compute costs, the system uses a **Daily Refresh with a 7-Day Rolling Window**.

* **Pacing:** The backend pipeline runs only once every 24 hours.  
* **Data Scope:** It processes the last 168 hours (7 days) of data, providing deep semantic stability.  
* **Output:** It generates a single, static data.json file that dictates the entire state of the 3D solar system for the next 24 hours.

## **4\. The AI / NLP Pipeline (Two-Phase Processing)**

The core challenge is categorizing 100,000+ posts into clean topics and labeling them without spending hundreds of dollars on LLM tokens. The solution is separating the sorting from the labeling.

### **Phase 1: Traditional NLP (The Sorter)**

* **Technology:** BERTopic utilizing HDBSCAN (Hierarchical Density-Based Spatial Clustering).  
* **Why HDBSCAN?** Instead of forcing 100,000 posts into 10 buckets (which creates garbage clusters), HDBSCAN finds dense conversational neighborhoods and throws the rest into an "Outlier/Noise" bucket (Topic \-1).  
* **The Workflow:** We embed the text, cluster it, discard the noise, and extract only the top 10 largest remaining clusters (The Planets). We run a secondary clustering pass on each planet to find its 6 largest sub-clusters (The Faces).

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

## **8\. Development Roadmap (Cursor MVP)**

* **Stage 1: Data Ingestion (5-8 hrs):** Write Python scripts to authenticate with Reddit/Bluesky APIs, pull 7 days of data, clean text (regex/spam filtering), and store in SQLite.  
* **Stage 2: The NLP Engine (15-20 hrs):** Implement BERTopic and HDBSCAN. Tune hyperparameters (like min\_cluster\_size) until the 10 topics and 6 sub-themes make logical sense on raw text.  
* **Stage 3: LLM Integration & Automation (3-5 hrs):** Write the prompt to force JSON extraction from the LLM. Format the final output to data.json. Wrap the script in a GitHub Actions YAML file to run daily.  
* **Stage 4: 3D Web Frontend (10-15 hrs):** Initialize a React Three Fiber project. Build the orbital physics, map the JSON data to cube dimensions and textures, and implement the click-to-rotate interaction mechanics.