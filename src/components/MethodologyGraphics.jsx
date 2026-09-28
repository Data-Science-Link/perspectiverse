function ArrowDown() {
  return (
    <svg className="method-arrow" viewBox="0 0 24 28" aria-hidden="true">
      <path d="M12 2v18M5 14l7 8 7-8" />
    </svg>
  )
}

export function OverviewGraphic() {
  return (
    <figure className="method-figure">
      <svg
        className="method-overview"
        viewBox="0 0 320 430"
        role="img"
        aria-labelledby="overview-graphic-title overview-graphic-desc"
      >
        <title id="overview-graphic-title">How Perspectiverse connects public talk to a sky you can look around</title>
        <desc id="overview-graphic-desc">
          Public posts from a week of conversation are clustered once a day into ten topics.
          Each topic splits into two to six opinions. You open the sky and check where you stand.
        </desc>
        <rect x="12" y="10" width="296" height="78" rx="16" fill="rgba(255,255,255,0.03)" stroke="rgba(232,230,245,0.12)" />
        <circle cx="46" cy="40" r="7" fill="#6ea8ff" />
        <circle cx="68" cy="52" r="5" fill="#c77dff" />
        <circle cx="58" cy="62" r="4" fill="#2fd2a8" />
        <circle cx="78" cy="38" r="6" fill="#ff6b9d" />
        <text x="102" y="42" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">A week of public posts</text>
        <text x="102" y="64" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">Usually English Bluesky</text>

        <path d="M160 88 v22" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 104 l6 10 6-10" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="118" width="296" height="78" rx="16" fill="rgba(255,255,255,0.03)" stroke="rgba(232,230,245,0.12)" />
        <rect x="36" y="140" width="44" height="34" rx="8" fill="#10131c" stroke="#f4c14e" />
        <path d="M48 151 h20 M58 141 v20" stroke="#f4c14e" strokeWidth="2" />
        <text x="102" y="150" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">Clustered once a day</text>
        <text x="102" y="172" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">One job. One snapshot.</text>

        <path d="M160 196 v22" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 212 l6 10 6-10" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="226" width="296" height="86" rx="16" fill="rgba(255,255,255,0.03)" stroke="rgba(232,230,245,0.12)" />
        <circle cx="58" cy="268" r="22" fill="#f4c14e" />
        <circle cx="52" cy="260" r="7" fill="rgba(255,255,255,0.22)" />
        <circle cx="88" cy="278" r="9" fill="#4aa3e6" />
        <text x="112" y="258" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">Ten planets</text>
        <text x="112" y="280" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">Size is share of attention</text>
        <text x="112" y="298" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">Longest spike = majority view</text>

        <path d="M160 312 v22" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 328 l6 10 6-10" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="342" width="296" height="76" rx="16" fill="rgba(244,193,78,0.08)" stroke="rgba(244,193,78,0.45)" />
        <circle cx="48" cy="380" r="10" fill="none" stroke="#f4c14e" strokeWidth="2" />
        <circle cx="48" cy="380" r="3" fill="#f4c14e" />
        <text x="74" y="374" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">You look around</text>
        <text x="74" y="396" fill="#f4e2b0" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">Check where your take stands</text>
      </svg>
      <figcaption>
        Public posts become ten planets. Each planet opens into a few opinions.
        You look around the sky — not a feed ranked for you.
      </figcaption>
    </figure>
  )
}

const STAGES = [
  {
    id: 'collect',
    kicker: '1 · Collect',
    title: 'Sample a week of talk',
    nodes: [
      {
        name: 'Bluesky search',
        detail: 'English posts from the last 168 hours. Default sample is small (200) so the job stays cheap; 10,000 is the fuller target.',
      },
      {
        name: 'Clean + SQLite',
        detail: 'Strip URLs, handles, and obvious spam. Keep the sample on the runner; it is not published.',
      },
    ],
  },
  {
    id: 'sort',
    kicker: '2 · Sort',
    title: 'Find neighborhoods in the words',
    nodes: [
      {
        name: 'TF-IDF + k-means',
        detail: 'The daily job uses lexical clustering. BERTopic is optional locally. Tiny clumps and noise (Topic −1) are dropped.',
      },
      {
        name: '10 planets',
        detail: 'The largest remaining clusters become the solar system. Size is share of kept posts, not importance.',
      },
      {
        name: '2–6 faces',
        detail: 'Each planet is split again. A cube is the ceiling. Face length is that view\'s share of the topic.',
      },
    ],
  },
  {
    id: 'name',
    kicker: '3 · Name',
    title: 'Label only the clusters',
    nodes: [
      {
        name: 'Ollama, then API, then fallback',
        detail: 'About 60 short prompts (10 × 6), never one per post. Heuristic titles from top terms if no model is available.',
      },
    ],
  },
  {
    id: 'publish',
    kicker: '4 · Publish',
    title: 'Ship a file, not a server',
    nodes: [
      {
        name: 'data.json',
        detail: 'One snapshot: topics, faces, a few example posts. This is the whole public sky.',
      },
      {
        name: 'GitHub Pages',
        detail: 'React + Three.js fetches the file. No API keys in the browser. Hosting stays near $0–$1 / month.',
      },
    ],
  },
]

export function TechnicalMapGraphic() {
  return (
    <figure className="method-figure">
      <svg
        className="method-overview"
        viewBox="0 0 320 520"
        role="img"
        aria-labelledby="tech-map-title tech-map-desc"
      >
        <title id="tech-map-title">Detailed path from Bluesky through the daily job to the static observatory</title>
        <desc id="tech-map-desc">
          Bluesky search feeds a GitHub Actions job that cleans posts, clusters ten planets
          and two to six faces, labels them, and writes data.json. GitHub Pages serves a
          React and Three.js observatory that only fetches that file.
        </desc>
        <text x="160" y="22" textAnchor="middle" fill="#f4c14e" fontSize="11" letterSpacing="2" fontFamily="Instrument Sans, Segoe UI, sans-serif">OUTSIDE THE BROWSER</text>

        <rect x="18" y="36" width="284" height="58" rx="14" fill="#10131c" stroke="rgba(110,168,255,0.55)" />
        <text x="160" y="60" textAnchor="middle" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">Bluesky public search</text>
        <text x="160" y="80" textAnchor="middle" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">7-day English window</text>

        <path d="M160 94 v20" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 108 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="18" y="118" width="284" height="58" rx="14" fill="#10131c" stroke="rgba(244,193,78,0.45)" />
        <text x="160" y="142" textAnchor="middle" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">GitHub Actions daily job</text>
        <text x="160" y="162" textAnchor="middle" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">Python · uv · SQLite on the runner</text>

        <path d="M160 176 v18" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M90 194 H230" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M90 194 v12" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M230 194 v12" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />

        <rect x="18" y="206" width="136" height="70" rx="14" fill="#10131c" stroke="rgba(47,210,168,0.45)" />
        <text x="86" y="234" textAnchor="middle" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, Segoe UI, sans-serif">Clean + cluster</text>
        <text x="86" y="254" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">TF-IDF · k-means</text>

        <rect x="166" y="206" width="136" height="70" rx="14" fill="#10131c" stroke="rgba(199,125,255,0.5)" />
        <text x="234" y="234" textAnchor="middle" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, Segoe UI, sans-serif">Label faces</text>
        <text x="234" y="254" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Ollama / API / terms</text>

        <path d="M86 276 v18" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M234 276 v18" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M86 294 H234" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M160 294 v16" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 304 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="18" y="314" width="284" height="58" rx="14" fill="rgba(244,193,78,0.08)" stroke="rgba(244,193,78,0.55)" />
        <text x="160" y="338" textAnchor="middle" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">public/data.json</text>
        <text x="160" y="358" textAnchor="middle" fill="#f4e2b0" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">10 planets · 2–6 faces · example posts</text>

        <path d="M160 372 v20" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 386 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <text x="160" y="412" textAnchor="middle" fill="#f4c14e" fontSize="11" letterSpacing="2" fontFamily="Instrument Sans, Segoe UI, sans-serif">IN THE BROWSER</text>
        <rect x="18" y="424" width="284" height="78" rx="14" fill="#10131c" stroke="rgba(232,230,245,0.16)" />
        <text x="160" y="454" textAnchor="middle" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">GitHub Pages observatory</text>
        <text x="160" y="476" textAnchor="middle" fill="#9a98ad" fontSize="12" fontFamily="Instrument Sans, Segoe UI, sans-serif">React · Three.js · fetch the file only</text>
      </svg>
      <figcaption>
        The expensive pieces stay on the daily runner. The page you open is a static
        snapshot: no Bluesky calls, no model keys, no server.
      </figcaption>
    </figure>
  )
}

export function SystemsGraphic() {
  return (
    <figure className="method-figure">
      <div className="systems-board" role="img" aria-labelledby="systems-graphic-title">
        <p id="systems-graphic-title" className="sr-only">
          Technical path from Bluesky search through cleaning, clustering, labeling,
          a static data file, and the React observatory on GitHub Pages.
        </p>
        {STAGES.map((stage, index) => (
          <div key={stage.id} className="systems-stage">
            {index > 0 && <ArrowDown />}
            <div className={`systems-card is-${stage.id}`}>
              <p className="systems-kicker">{stage.kicker}</p>
              <h3>{stage.title}</h3>
              <div className={`systems-nodes is-${stage.nodes.length}`}>
                {stage.nodes.map((node) => (
                  <article key={node.name} className="systems-node">
                    <h4>{node.name}</h4>
                    <p>{node.detail}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
      <figcaption>
        Heavy work happens once a day on GitHub Actions. The site you open is a static
        snapshot — the browser never talks to Bluesky or an LLM.
      </figcaption>
    </figure>
  )
}
