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
        viewBox="0 0 320 500"
        role="img"
        aria-labelledby="overview-graphic-title overview-graphic-desc"
      >
        <title id="overview-graphic-title">From Bluesky posts through Jev filters to planets and perspectives</title>
        <desc id="overview-graphic-desc">
          A week of English Bluesky posts passes spam, public-claim, and section filters, clusters into up to
          ten planets, splits into two to six perspectives by prevalence, then loads in the observatory.
        </desc>
        <rect x="12" y="10" width="296" height="64" rx="16" fill="rgba(255,255,255,0.03)" stroke="rgba(232,230,245,0.12)" />
        <text x="28" y="36" fill="#efeef7" fontSize="14" fontFamily="Instrument Sans, Segoe UI, sans-serif">Bluesky · 7-day English window</text>
        <text x="28" y="56" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Current source; broader inputs planned</text>

        <path d="M160 74 v18" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 86 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="96" width="296" height="72" rx="16" fill="rgba(244,193,78,0.08)" stroke="rgba(244,193,78,0.45)" />
        <text x="28" y="120" fill="#f4e2b0" fontSize="13" fontFamily="Instrument Sans, Segoe UI, sans-serif">Jev filters</text>
        <text x="28" y="140" fill="#efeef7" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Spam drop · public-claim check · newspaper section</text>
        <text x="28" y="158" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Regex fallback when Jev is off</text>

        <path d="M160 168 v18" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 180 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="190" width="296" height="64" rx="16" fill="rgba(255,255,255,0.03)" stroke="rgba(232,230,245,0.12)" />
        <text x="28" y="216" fill="#efeef7" fontSize="14" fontFamily="Instrument Sans, Segoe UI, sans-serif">Cluster once a day</text>
        <text x="28" y="236" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Embeddings → up to 10 planets</text>

        <path d="M160 254 v18" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 266 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="276" width="296" height="78" rx="16" fill="rgba(255,255,255,0.03)" stroke="rgba(232,230,245,0.12)" />
        <circle cx="52" cy="314" r="18" fill="#f4c14e" />
        <circle cx="82" cy="324" r="10" fill="#4aa3e6" />
        <text x="108" y="308" fill="#efeef7" fontSize="14" fontFamily="Instrument Sans, Segoe UI, sans-serif">Planets = topics</text>
        <text x="108" y="328" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Size = attention share</text>
        <text x="108" y="344" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">2–6 perspectives · bars by prevalence</text>

        <path d="M160 354 v18" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 366 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="376" width="296" height="64" rx="16" fill="rgba(47,210,168,0.08)" stroke="rgba(47,210,168,0.45)" />
        <text x="28" y="402" fill="#efeef7" fontSize="14" fontFamily="Instrument Sans, Segoe UI, sans-serif">Steelmanned summaries</text>
        <text x="28" y="422" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Not a right/wrong score · static data.json</text>
      </svg>
      <figcaption>
        Filters first, then clustering and labels. The browser only fetches the published file.
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
        detail: 'English posts from the last 168 hours. The job holds up to 10,000 that already passed cleaning, dedup, spam, and the public-claim check.',
      },
      {
        name: 'Clean + SQLite',
        detail: 'Strip URLs and handles, drop spam, and keep public claims. The window stays in SQLite. The site publishes only the snapshot.',
      },
    ],
  },
  {
    id: 'sort',
    kicker: '2 · Sort',
    title: 'Find neighborhoods in the words',
    nodes: [
      {
        name: 'MiniLM embeddings',
        detail: 'The daily job embeds with a local MiniLM model and keeps tight groups. Tests use TF-IDF. Tiny clumps and noise (Topic −1) are dropped.',
      },
      {
        name: '10 planets',
        detail: 'The largest tight groups become the solar system, and the job stops at ten. Size is share of kept posts, not importance.',
      },
      {
        name: '2–6 perspectives',
        detail: 'One stance stays one perspective. Another is added only when it is large and different. Bar length is that view’s share of the planet.',
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
        detail: 'One short prompt per planet and per perspective, never one per post. If no model answers, the summary is a sentence from a shown post.',
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
        detail: 'One snapshot: topics, perspectives, a few example posts. This is the whole public solar system.',
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
          Bluesky search feeds a GitHub Actions job that cleans posts, clusters up to ten planets
          and two to six perspectives, labels them, and writes data.json. GitHub Pages serves a
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
        <text x="86" y="254" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">MiniLM embeddings</text>

        <rect x="166" y="206" width="136" height="70" rx="14" fill="#10131c" stroke="rgba(199,125,255,0.5)" />
        <text x="234" y="234" textAnchor="middle" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, Segoe UI, sans-serif">Label views</text>
        <text x="234" y="254" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">Ollama / API / terms</text>

        <path d="M86 276 v18" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M234 276 v18" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M86 294 H234" fill="none" stroke="rgba(244,193,78,0.45)" strokeWidth="2" />
        <path d="M160 294 v16" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 304 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="18" y="314" width="284" height="58" rx="14" fill="rgba(244,193,78,0.08)" stroke="rgba(244,193,78,0.55)" />
        <text x="160" y="338" textAnchor="middle" fill="#efeef7" fontSize="15" fontFamily="Instrument Sans, Segoe UI, sans-serif">public/data.json</text>
        <text x="160" y="358" textAnchor="middle" fill="#f4e2b0" fontSize="11" fontFamily="Instrument Sans, Segoe UI, sans-serif">≤10 planets · 2–6 views · example posts</text>

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
