import { useCallback, useEffect, useRef, useState } from 'react'
import { SITE_TAGLINE, setWelcomeHidden } from '../lib/copy'

function PlanetSizeGraphic() {
  return (
    <figure className="welcome-graphic">
      <svg viewBox="0 0 320 240" role="img" aria-labelledby="size-graphic-title">
        <title id="size-graphic-title">Bigger planet, bigger share</title>
        <defs>
          <radialGradient id="welcome-sun" cx="36%" cy="32%" r="68%">
            <stop offset="0%" stopColor="#ffe7a8" />
            <stop offset="58%" stopColor="#f4c14e" />
            <stop offset="100%" stopColor="#c48a22" />
          </radialGradient>
          <radialGradient id="welcome-earth" cx="36%" cy="32%" r="68%">
            <stop offset="0%" stopColor="#d7f2ff" />
            <stop offset="48%" stopColor="#4aa3e6" />
            <stop offset="100%" stopColor="#1d4e78" />
          </radialGradient>
          <radialGradient id="welcome-mars" cx="36%" cy="32%" r="68%">
            <stop offset="0%" stopColor="#ffd0bc" />
            <stop offset="55%" stopColor="#e25a2b" />
            <stop offset="100%" stopColor="#7a2c12" />
          </radialGradient>
          <radialGradient id="welcome-ice" cx="36%" cy="32%" r="68%">
            <stop offset="0%" stopColor="#f3fffd" />
            <stop offset="55%" stopColor="#7ee0d8" />
            <stop offset="100%" stopColor="#1d6b66" />
          </radialGradient>
        </defs>
        <line x1="28" y1="168" x2="292" y2="168" stroke="rgba(239,238,247,0.16)" />
        <circle cx="62" cy="124" r="44" fill="url(#welcome-sun)" />
        <circle cx="142" cy="136" r="32" fill="url(#welcome-earth)" />
        <circle cx="210" cy="146" r="22" fill="url(#welcome-mars)" />
        <circle cx="266" cy="154" r="14" fill="url(#welcome-ice)" />
        <text x="62" y="196" textAnchor="middle" fill="#efeef7" fontSize="14" fontFamily="system-ui, sans-serif">42%</text>
        <text x="142" y="196" textAnchor="middle" fill="#efeef7" fontSize="14" fontFamily="system-ui, sans-serif">28%</text>
        <text x="210" y="196" textAnchor="middle" fill="#efeef7" fontSize="14" fontFamily="system-ui, sans-serif">18%</text>
        <text x="266" y="196" textAnchor="middle" fill="#efeef7" fontSize="14" fontFamily="system-ui, sans-serif">12%</text>
        <text x="160" y="226" textAnchor="middle" fill="#f4e2b0" fontSize="15" fontFamily="Georgia, serif">Bigger planet, bigger share.</text>
      </svg>
    </figure>
  )
}

function ReadingGraphic() {
  return (
    <figure className="welcome-graphic">
      <svg viewBox="0 0 320 240" role="img" aria-labelledby="reading-graphic-title">
        <title id="reading-graphic-title">Bars, then the summary</title>
        <rect x="28" y="8" width="264" height="224" rx="22" fill="#0c0e16" stroke="rgba(239,238,247,0.2)" />
        <rect x="44" y="22" width="150" height="16" rx="8" fill="#f4c14e" />
        <rect x="44" y="44" width="104" height="16" rx="8" fill="#4aa3e6" />
        <rect x="44" y="66" width="68" height="16" rx="8" fill="#e25a2b" />
        <text x="204" y="35" fill="#efeef7" fontSize="12" fontFamily="system-ui, sans-serif">42%</text>
        <text x="158" y="57" fill="#efeef7" fontSize="12" fontFamily="system-ui, sans-serif">28%</text>
        <text x="122" y="79" fill="#efeef7" fontSize="12" fontFamily="system-ui, sans-serif">18%</text>
        <text x="48" y="112" fill="#f4e2b0" fontSize="13" fontFamily="Georgia, serif">Summary</text>
        <rect x="48" y="124" width="196" height="6" rx="3" fill="rgba(239,238,247,0.82)" />
        <rect x="48" y="138" width="168" height="6" rx="3" fill="rgba(239,238,247,0.55)" />
        <rect x="48" y="152" width="124" height="6" rx="3" fill="rgba(239,238,247,0.32)" />
        <rect x="44" y="176" width="232" height="40" rx="10" fill="#10131c" stroke="rgba(239,238,247,0.1)" />
        <rect x="56" y="188" width="180" height="5" rx="2" fill="rgba(239,238,247,0.28)" />
        <rect x="56" y="200" width="132" height="5" rx="2" fill="rgba(239,238,247,0.16)" />
      </svg>
    </figure>
  )
}

export default function WelcomeModal({ open, onClose }) {
  const cardRef = useRef(null)
  const [dontShow, setDontShow] = useState(false)

  const dismiss = useCallback(() => {
    if (dontShow) setWelcomeHidden(true)
    onClose()
  }, [dontShow, onClose])

  useEffect(() => {
    if (!open) return undefined
    const previous = document.activeElement
    cardRef.current?.focus()
    const onKey = (event) => {
      if (event.key === 'Escape') dismiss()
    }
    document.addEventListener('keydown', onKey)
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = original
      if (previous instanceof HTMLElement) previous.focus()
    }
  }, [open, dismiss])

  if (!open) return null

  return (
    <div className="welcome-layer">
      <aside
        ref={cardRef}
        className="welcome-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
        tabIndex={-1}
      >
        <header className="welcome-head">
          <h2 id="welcome-title">Perspectiverse</h2>
          <p className="welcome-tagline">{SITE_TAGLINE}</p>
        </header>
        <div className="welcome-body">
          <div className="welcome-graphics">
            <PlanetSizeGraphic />
            <ReadingGraphic />
          </div>
        </div>
        <footer className="welcome-foot">
          <label className="welcome-dont">
            <input
              type="checkbox"
              checked={dontShow}
              onChange={(event) => setDontShow(event.target.checked)}
            />
            Don&apos;t show this again
          </label>
          <button type="button" className="welcome-enter" onClick={dismiss}>
            Enter the solar system
          </button>
        </footer>
      </aside>
      <button type="button" className="welcome-backdrop" aria-label="Close welcome" onClick={dismiss} />
    </div>
  )
}
