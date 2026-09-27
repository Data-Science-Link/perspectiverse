export default function PerspectiverseGraphic({ compact = false }) {
  return (
    <figure className={`pv-graphic ${compact ? 'is-compact' : ''}`}>
      <svg viewBox="0 0 360 220" role="img" aria-labelledby="pv-graphic-title pv-graphic-desc">
        <title id="pv-graphic-title">How Perspectiverse is shaped</title>
        <desc id="pv-graphic-desc">
          A sun at the center, orbiting planets, and one opened crystal whose faces are its
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
          <polygon points="0,-36 18,-10 0,8 -18,-10" fill="#f4c14e" />
          <polygon points="0,36 18,10 0,-8 -18,10" fill="#ff7a3d" />
          <polygon points="36,0 10,16 -8,0 10,-16" fill="#6ea8ff" />
          <polygon points="-36,0 -10,16 8,0 -10,-16" fill="#c77dff" />
          <polygon points="20,26 12,4 -4,8 6,20" fill="#2fd2a8" />
          <polygon points="-20,-26 -12,-4 4,-8 -6,-20" fill="#ff6b9d" />
        </g>
        <text x="124" y="204" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, sans-serif">
          Topics orbit by volume
        </text>
        <text x="268" y="204" textAnchor="middle" fill="#9a98ad" fontSize="11" fontFamily="Instrument Sans, sans-serif">
          Open it: two to six views
        </text>
      </svg>
      {!compact && (
        <figcaption>
          The largest topic is the sun. The next nine take solar-system skins in order:
          Mercury through Pluto. Size is attention. Open a planet and the sphere dissolves
          into a crystal: two to six faces, gold first, length by share of posts.
        </figcaption>
      )}
    </figure>
  )
}
