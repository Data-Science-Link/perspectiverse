export default function WelcomeHowItWorks() {
  return (
    <figure className="welcome-graphic welcome-flow">
      <svg
        viewBox="0 0 320 392"
        preserveAspectRatio="xMidYMin meet"
        role="img"
        aria-labelledby="welcome-flow-title welcome-flow-desc"
        style={{ display: 'block', width: '100%', height: 'auto' }}
      >
        <title id="welcome-flow-title">How Perspectiverse maps a week of public talk</title>
        <desc id="welcome-flow-desc">
          English Bluesky posts pass spam, public-claim, and newspaper-section filters, cluster into up to
          ten planets, split into two to six perspectives by prevalence, then appear as a solar system with
          bars and summaries — not a ranking of who is right.
        </desc>

        <rect x="12" y="4" width="296" height="52" rx="12" fill="rgba(255,255,255,0.05)" stroke="rgba(232,230,245,0.16)" />
        <text x="26" y="26" fill="#efeef7" fontSize="16" fontFamily="Instrument Sans, system-ui, sans-serif">Bluesky (today&apos;s source)</text>
        <text x="26" y="44" fill="#9a98ad" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">Free API now · broader inputs later</text>

        <path d="M160 56 v10" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 62 l6 7 6-7" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="68" width="296" height="58" rx="12" fill="rgba(244,193,78,0.08)" stroke="rgba(244,193,78,0.4)" />
        <text x="26" y="90" fill="#f4e2b0" fontSize="16" fontFamily="Instrument Sans, system-ui, sans-serif">Jev filters</text>
        <text x="26" y="110" fill="#efeef7" fontSize="14" fontFamily="Instrument Sans, system-ui, sans-serif">Spam drop · public claim · newspaper section</text>

        <path d="M160 126 v10" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 132 l6 7 6-7" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="138" width="296" height="54" rx="12" fill="rgba(255,255,255,0.05)" stroke="rgba(232,230,245,0.16)" />
        <circle cx="44" cy="164" r="14" fill="#f4c14e" />
        <circle cx="66" cy="170" r="8" fill="#4aa3e6" />
        <text x="88" y="158" fill="#efeef7" fontSize="16" fontFamily="Instrument Sans, system-ui, sans-serif">Up to 10 planets</text>
        <text x="88" y="176" fill="#9a98ad" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">Topics · size = attention share</text>

        <path d="M160 192 v10" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 198 l6 7 6-7" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="204" width="296" height="54" rx="12" fill="rgba(255,255,255,0.05)" stroke="rgba(232,230,245,0.16)" />
        <rect x="26" y="222" width="64" height="9" rx="4" fill="#4aa3e6" />
        <rect x="26" y="236" width="42" height="9" rx="4" fill="rgba(74,163,230,0.55)" />
        <text x="98" y="224" fill="#efeef7" fontSize="16" fontFamily="Instrument Sans, system-ui, sans-serif">2–6 perspectives</text>
        <text x="98" y="242" fill="#9a98ad" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">By prevalence · steelmanned</text>

        <path d="M160 258 v10" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />
        <path d="M154 264 l6 7 6-7" fill="none" stroke="rgba(244,193,78,0.7)" strokeWidth="2" />

        <rect x="12" y="270" width="296" height="52" rx="12" fill="rgba(47,210,168,0.1)" stroke="rgba(47,210,168,0.45)" />
        <text x="26" y="294" fill="#efeef7" fontSize="16" fontFamily="Instrument Sans, system-ui, sans-serif">Explore the solar system</text>
        <text x="26" y="312" fill="#9a98ad" fontSize="13" fontFamily="Instrument Sans, system-ui, sans-serif">Bars · summaries · example posts</text>
      </svg>
      <figcaption>
        One daily snapshot: filtered posts → topics → views. We show what showed up, as fairly as we can.
      </figcaption>
    </figure>
  )
}
