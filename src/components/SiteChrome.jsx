function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  )
}

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 5 7 12l8 7" />
    </svg>
  )
}

export default function SiteChrome({
  drilled = false,
  title = 'Perspectiverse',
  subtitle = 'See every perspective — and where yours stands.',
  tagline = false,
  backLabel = 'Back',
  onBack,
  onOpenMenu,
}) {
  return (
    <header className="site-chrome">
      {drilled ? (
        <button
          type="button"
          className="icon-btn"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            onBack()
          }}
          aria-label={backLabel}
        >
          <BackIcon />
        </button>
      ) : (
        <button type="button" className="icon-btn" onClick={onOpenMenu} aria-label="Open menu">
          <MenuIcon />
        </button>
      )}
      <div className="site-chrome-copy">
        <p className="site-chrome-title">{title}</p>
        {subtitle && (
          <p className={`site-chrome-sub ${tagline ? 'is-tagline' : ''}`}>{subtitle}</p>
        )}
      </div>
      {drilled && (
        <button type="button" className="icon-btn" onClick={onOpenMenu} aria-label="Open menu">
          <MenuIcon />
        </button>
      )}
    </header>
  )
}
