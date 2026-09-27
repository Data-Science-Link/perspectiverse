export default function PerspectiverseGraphic({ compact = false }) {
  return (
    <figure className={`pv-graphic ${compact ? 'is-compact' : ''}`}>
      <svg viewBox="0 0 360 220" role="img" aria-labelledby="pv-graphic-title pv-graphic-desc">
        <title id="pv-graphic-title">How Perspectiverse is shaped</title>
        <desc id="pv-graphic-desc">
          A sun at the center, orbiting planets, and one cube whose six spikes are six
          perspectives.
        </desc>
        <rect width="360" height="220" rx="18" fill="#070914" />
        <ellipse cx="124" cy="110" rx="96" ry="62" fill="none" stroke="rgba(232,230,245,0.16)" />
        <ellipse cx="124" cy="110" rx="68" ry="42" fill="none" stroke="rgba(232,230,245,0.22)" />
        <ellipse cx="124" cy="110" rx="40" ry="24" fill="none" stroke="rgba(232,230,245,0.28)" />
        <circle cx="124" cy="110" r="16" fill="#f4c14e" />
        <circle cx="124" cy="110" r="22" fill="none" stroke="rgba(244,193,78,0.35)" />
        <circle cx="196" cy="78" r="7" fill="#b5a394" />
        <circle cx="204" cy="142" r="8" fill="#3d8fd1" />
        <circle cx="62" cy="70" r="9" fill="#c1440e" />
        <circle cx="48" cy="150" r="11" fill="#d4a056" />
        <g transform="translate(268 110)">
          <polygon points="0,-38 16,-8 0,8 -16,-8" fill="#ffe08a" />
          <polygon points="0,38 16,8 0,-8 -16,8" fill="#ff8b5c" />
          <polygon points="38,0 8,16 -8,0 8,-16" fill="#7ee0c2" />
          <polygon points="-38,0 -8,16 8,0 -8,-16" fill="#7eb6ff" />
          <polygon points="22,28 14,4 -4,8 6,22" fill="#f08ab0" />
          <polygon points="-22,-28 -14,-4 4,-8 -6,-22" fill="#d2b0ff" />
          <rect x="-11" y="-11" width="22" height="22" rx="3" fill="#e6d3a3" />
        </g>
        <text x="124" y="204" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, sans-serif">
          Topics orbit by volume
        </text>
        <text x="268" y="204" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, sans-serif">
          Six spikes, six views
        </text>
      </svg>
      {!compact && (
        <figcaption>
          The largest topic is the sun. The next nine take solar-system skins in order:
          Mercury through Pluto. Spike length is share of the conversation, not truth.
        </figcaption>
      )}
    </figure>
  )
}
