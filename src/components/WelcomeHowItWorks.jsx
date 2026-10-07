export default function WelcomeHowItWorks() {
  return (
    <figure className="welcome-graphic welcome-flow">
      <svg
        viewBox="0 0 320 420"
        role="img"
        aria-labelledby="welcome-flow-title welcome-flow-desc"
      >
        <title id="welcome-flow-title">How Perspectiverse maps a week of public talk</title>
        <desc id="welcome-flow-desc">
          English Bluesky posts pass spam, public-claim, and newspaper-section filters, cluster into up to
          ten planets, split into two to six perspectives by prevalence, then appear as a solar system with
          bars and summaries — not a ranking of who is right.
        </desc>

        <rect x="16" y="8" width="288" height="56" rx="14" fill="rgba(255,255,255,0.04)" stroke="rgba(232,230,245,0.14)" />
        <text x="32" y="30" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">Bluesky (today&apos;s source)</text>
        <text x="32" y="50" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, system-ui, sans-serif">Free public API · more inputs hoped for later</text>

        <path d="M160 64 v14" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />
        <path d="M154 74 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />

        <rect x="16" y="82" width="288" height="72" rx="14" fill="rgba(244,193,78,0.06)" stroke="rgba(244,193,78,0.35)" />
        <text x="32" y="104" fill="#f4e2b0" fontSize="12" fontFamily="Instrument Sans, system-ui, sans-serif">Jev filters (per post)</text>
        <text x="32" y="124" fill="#efeef7" fontSize="11" fontFamily="Instrument Sans, system-ui, sans-serif">Drop spam · keep public claims · newspaper section</text>
        <text x="32" y="142" fill="#9a98ad" fontSize="10" fontFamily="Instrument Sans, system-ui, sans-serif">So planets reflect discourse, not ads or noise</text>

        <path d="M160 154 v14" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />
        <path d="M154 164 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />

        <rect x="16" y="172" width="288" height="64" rx="14" fill="rgba(255,255,255,0.04)" stroke="rgba(232,230,245,0.14)" />
        <circle cx="48" cy="204" r="18" fill="#f4c14e" />
        <circle cx="78" cy="214" r="10" fill="#4aa3e6" />
        <circle cx="98" cy="218" r="7" fill="#e25a2b" />
        <text x="118" y="198" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">Up to 10 planets (topics)</text>
        <text x="118" y="218" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, system-ui, sans-serif">Size = share of attention in the sample</text>

        <path d="M160 236 v14" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />
        <path d="M154 246 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />

        <rect x="16" y="254" width="288" height="64" rx="14" fill="rgba(255,255,255,0.04)" stroke="rgba(232,230,245,0.14)" />
        <rect x="32" y="276" width="72" height="10" rx="5" fill="#4aa3e6" />
        <rect x="32" y="292" width="48" height="10" rx="5" fill="rgba(74,163,230,0.55)" />
        <rect x="32" y="308" width="28" height="10" rx="5" fill="rgba(74,163,230,0.35)" />
        <text x="118" y="286" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">2–6 perspectives (faces)</text>
        <text x="118" y="306" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, system-ui, sans-serif">Shown by prevalence · steelmanned, not scored</text>

        <path d="M160 318 v14" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />
        <path d="M154 328 l6 8 6-8" fill="none" stroke="rgba(244,193,78,0.65)" strokeWidth="2" />

        <rect x="16" y="336" width="288" height="68" rx="14" fill="rgba(47,210,168,0.08)" stroke="rgba(47,210,168,0.4)" />
        <text x="32" y="362" fill="#efeef7" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">You explore the solar system</text>
        <text x="32" y="382" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, system-ui, sans-serif">Bars, summaries, example posts — see where your take sits</text>
      </svg>
      <figcaption>
        One daily snapshot: filtered public posts → topics → views. We show what showed up, as fairly as we can.
      </figcaption>
    </figure>
  )
}
