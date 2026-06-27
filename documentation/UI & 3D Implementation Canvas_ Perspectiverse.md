# **UI & 3D Implementation Canvas: Perspectiverse**

**Core UI Philosophy:** A split-screen analytical experience. The left 2/3 of the screen is an immersive, passive 3D observatory. The right 1/3 is an active, data-rich analytical sidebar that reacts to 3D interactions.

## **1\. The Visual Mechanics**

### **The 3D Canvas (Left 2/3)**

* **The Sun:** The \#1 topic sits at \[0,0,0\].  
* **The Planets:** Topics 2-10 orbit the center at varying distances.  
* **The Labels:** Floating 3D text (or screen-space HTML) sits slightly above each planet, showing only the 2-word topic name (e.g., "AI Regulation").  
* **The Animation:** All planets orbit the center continuously. Simultaneously, each planet rotates on its own X/Y/Z axes so the user can see all 6 faces spinning.  
* **The Geometry (The Spiky Cubes):**  
  * A standard cube has flat faces. We will modify this so each of the 6 faces acts like the base of a 4-sided pyramid.  
  * The height (extrusion) of that pyramid's peak is driven directly by the percentage of conversation volume for that perspective.  
  * *Result:* A perspective with 50% volume creates a massive spike on one side, while the remaining 5 perspectives (10% each) have tiny bumps.

### **The Analytical Sidebar (Right 1/3)**

* **Default State (No Selection):** Welcome text, project philosophy, instructions on how to navigate the 3D space, and high-level global stats (total posts analyzed this week).  
* **Topic Selected State (Clicking a Planet):**  
  * The 3D camera smoothly flies to and locks onto the selected planet.  
  * The sidebar updates: Shows an isolated, spinning render of the spiky cube at the top.  
  * Below it: A list of the 6 perspectives with their full titles, 1-sentence summaries, and a horizontal bar chart showing their volume %.  
* **Perspective Selected State (Clicking a Bar Chart / Face):**  
  * The sidebar drills down further.  
  * It displays the specific perspective details.  
  * Below that: A scrollable feed of the actual representative Bluesky posts that formed this cluster, sorted by like count descending.

## **2\. Technical Stack Implications**

To pull this off without writing thousands of lines of complex WebGL code, we use the React ecosystem.

* **UI Framework:** React (via Vite).  
* **Styling:** Tailwind CSS (perfect for rapidly building the sidebar and horizontal bar charts).  
* **3D Engine:** Three.js wrapped in @react-three/fiber (R3F). R3F allows you to build 3D scenes using React components.  
* **3D Helpers:** @react-three/drei. This is a library of pre-built R3F tools. We will use it for:  
  * \<OrbitControls\> (Camera movement).  
  * \<Html\> (Pinning DOM text labels to 3D coordinates).  
  * \<CameraControls\> (For smooth flying/zooming when a planet is clicked).  
* **State Management:** React useState / useContext (To pass the "selected ID" from the 3D canvas to the Sidebar).

### **Changes Needed to Your Backend data.json:**

To power this UI, your Python pipeline must output a very specific JSON structure. It needs the aggregate data *and* the raw posts.

{  
  "last\_updated": "2026-06-04",  
  "total\_posts": 100000,  
  "topics": \[  
    {  
      "id": 1,  
      "name": "Artificial Intelligence",  
      "total\_volume\_percent": 35.5,  
      "perspectives": \[  
        {  
          "id": "1A",  
          "title": "Job Replacement Fear",  
          "summary": "Users are heavily anxious about recent layoffs attributed to automation.",  
          "volume\_percent": 45.0,  
          "representative\_posts": \[  
            {"author": "user1.bsky", "text": "Just lost my copywriting gig to an LLM...", "likes": 402},  
            {"author": "user2.bsky", "text": "The tech bros don't care about the working class.", "likes": 150}  
          \]  
        }  
        // ... 5 more perspectives  
      \]  
    }  
  \]  
}

## **3\. Stages of Buildout (From Simple to Complex)**

### **Phase 1: The 2D React Shell & State (2-4 hours)**

* **Goal:** Build the layout without worrying about 3D math yet.  
* **Tasks:**  
  1. Set up Vite \+ React \+ Tailwind.  
  2. Create a CSS Grid or Flexbox layout: Left div (70% width), Right div (30% width).  
  3. Load dummy data.json into a React state variable.  
  4. Build the Sidebar components that toggle based on a selectedTopic state variable. Ensure the horizontal bar charts map correctly to the data.

### **Phase 2: The Basic 3D Solar System (4-6 hours)**

* **Goal:** Get flat cubes orbiting on the screen.  
* **Tasks:**  
  1. Install three, @react-three/fiber, and @react-three/drei.  
  2. Map through your topics array and render a standard \<mesh\> with a \<boxGeometry\> for each.  
  3. Use useFrame to calculate circular orbits around the center based on time and distance.  
  4. Use Drei's \<Html\> component to attach floating labels above each cube.  
  5. Add onClick handlers to the meshes that update the selectedTopic React state, verifying that clicking a cube changes the sidebar.

### **Phase 3: Building the "Spiky Cube" Geometry (5-8 hours)**

* **Goal:** Translate percentage data into physical shape.  
* **Tasks:**  
  * *The Technical Solution:* Don't try to mathematically distort a standard box. Instead, create a custom React component called \<SpikyCube\>.  
  * Inside \<SpikyCube\>, render a small central BoxGeometry.  
  * Attach 6 ConeGeometry meshes (with 4 radial segments, making them square pyramids) to the 6 faces of the central box.  
  * Map the volume\_percent of your 6 perspectives to the scale-y (height) of those 6 respective pyramids.  
  * Apply a useFrame rotation to the whole group so the lopsided star/cube tumbles through space.

### **Phase 4: Camera Animations & Polish (3-5 hours)**

* **Goal:** Make the experience feel cinematic.  
* **Tasks:**  
  1. When a user clicks a planet, use Drei's \<CameraControls\> to interpolate (fly) the camera from its current position to a close-up offset of the selected planet.  
  2. Blur or dim the unselected planets.  
  3. Ensure that clicking a perspective in the sidebar highlights the corresponding "spike" on the 3D model (e.g., changing its color to an emissive neon).