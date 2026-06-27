# **Technical Implementation Canvas: Perspectiverse**

**Core Philosophy:** Lightweight, local-first data processing, outputting to a static, serverless frontend.

## **1\. Environment & Architecture**

* **IDE:** Cursor  
* **Version Control:** Git / GitHub  
* **Python Manager:** uv (for ultra-fast virtual environments and dependency management)  
* **LLM Engine:** Ollama (running locally to avoid all API costs and rate limits)  
* **Frontend:** Vite \+ React \+ React Three Fiber (compiles to static HTML/JS for GitHub Pages)

### **Directory Structure**

perspectiverse/  
├── docs/                 \# Markdown documentation  
├── pipeline/             \# Python backend code  
│   ├── data/             \# Local storage (SQLite / raw JSONs)  
│   ├── run\_pipeline.py   \# Main orchestrator script  
│   └── requirements.txt  \# Managed via uv  
├── public/               \# Static web assets  
│   ├── index.html  
│   └── data.json         \# THE BRIDGE: Output of pipeline, input for frontend  
└── src/                  \# React / Three.js frontend code

## **2\. Stage-by-Stage Implementation**

### **Stage 1: Local Setup & Tooling (1-2 Hours)**

1. **Initialize Git:** git init  
2. **Setup Python:** uv venv and activate it.  
3. **Install Core Python Libs:** uv pip install atproto pandas bertopic ollama  
4. **Install Local AI:** Download Ollama to your OS, and pull a fast, lightweight model suitable for JSON extraction: ollama run llama3 (or phi3 for even faster local processing).  
5. **Setup Frontend:** Run npm create vite@latest . \--template react in the root (or a subfolder), and install Three.js: npm install three @react-three/fiber @react-three/drei.

### **Stage 2: Bluesky Data Ingestion (3-5 Hours)**

* **Goal:** Pull a random sample of English posts from the last 7 days.  
* **The Script:** Write a Python script using atproto.  
* **The Logic:**  
  1. Authenticate with an App Password.  
  2. Query the Bluesky search API for posts between \[Date \- 7 days\] and \[Today\].  
  3. Fetch a large batch (e.g., 20,000 posts).  
  4. Use Python's random.sample() to randomly select 10,000 posts to ensure a diverse, non-chronological slice of the internet.  
  5. Clean text (remove URLs, handles) and save to a local posts.csv or SQLite.

### **Stage 3: The Sorter (Traditional NLP) (5-8 Hours)**

* **Goal:** Find the 10 Planets and 60 Faces using BERTopic.  
* **The Script:**  
  1. Load the 10,000 cleaned posts.  
  2. Embed and cluster using BERTopic (which uses all-MiniLM-L6-v2 locally by default—very fast).  
  3. Filter out Topic \-1 (the noise).  
  4. Isolate the top 10 largest remaining clusters (Planets). Save their sizes (Volume).  
  5. For each of the 10 Planets, take its posts and run a K-Means cluster (n\_clusters=6) to find the 6 Faces.  
  6. Extract the top 20 most representative posts for each of the 60 Faces.

### **Stage 4: The Explainer (Local LLM via Ollama) (4-6 Hours)**

* **Goal:** Generate the human-readable labels for the cubes.  
* **The Script:**  
  1. Use the official ollama Python library.  
  2. Loop through the 60 Faces. For each, send the 20 representative posts to your local Llama-3 model.  
  3. **The Prompt:** *"Read these posts. Output ONLY a valid JSON object with two keys: 'title' (max 3 words) and 'summary' (max 1 sentence)."*  
  4. Parse the JSON response.  
  5. **Compile final output:** Assemble the planetary sizes, cluster coordinates, and the 60 LLM labels into a single data.json file. Save this to the /public folder.

### **Stage 5: The 3D Frontend (10-15 Hours)**

* **Goal:** Visualize data.json in the browser.  
* **The Logic:**  
  1. **The Sun:** Calculate the biggest volume and place it at \[0,0,0\].  
  2. **The Planets:** Map the remaining 9 topics to orbital paths around the sun based on size.  
  3. **The Cubes:** Render each planet as a BoxGeometry.  
  4. **The Textures:** Use React Three Fiber's HTML overlays or Canvas textures to map the LLM JSON summaries to the 6 faces of each respective cube.  
  5. **Interaction:** Add an onClick event to lock the camera to a cube, and onDrag to rotate it.

### **Stage 6: Deployment (1-2 Hours)**

* **Backend:** Remains completely local. Whenever you want to update the data, you run python pipeline/run\_pipeline.py on your laptop. It overwrites public/data.json.  
* **Frontend:**  
  1. Commit the updated data.json and the frontend code to Git.  
  2. Configure GitHub Pages in your repo settings to deploy from your main branch.  
  3. GitHub Actions automatically builds the Vite/React app and publishes it to a live URL for the world to see.