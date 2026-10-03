import { useCallback, useEffect, useRef, useState } from 'react'
import { SITE_TAGLINE, setWelcomeHidden } from '../lib/copy'

function BarsGraphic() {
  return (
    <figure className="welcome-graphic">
      <svg viewBox="0 0 320 240" role="img" aria-labelledby="bars-graphic-title">
        <title id="bars-graphic-title">Longer bars are the larger shares</title>
        <rect x="16" y="28" width="248" height="32" rx="8" fill="#8a6a22" />
        <rect x="16" y="20" width="248" height="32" rx="8" fill="#f4c14e" />
        <rect x="16" y="20" width="248" height="12" rx="6" fill="#ffe7a3" opacity="0.85" />
        <rect x="16" y="84" width="168" height="32" rx="8" fill="#1d4e78" />
        <rect x="16" y="76" width="168" height="32" rx="8" fill="#4aa3e6" />
        <rect x="16" y="76" width="168" height="12" rx="6" fill="#c5e6ff" opacity="0.8" />
        <rect x="16" y="140" width="112" height="32" rx="8" fill="#7a2c12" />
        <rect x="16" y="132" width="112" height="32" rx="8" fill="#e25a2b" />
        <rect x="16" y="132" width="112" height="12" rx="6" fill="#ffc2a8" opacity="0.75" />
        <rect x="16" y="196" width="68" height="32" rx="8" fill="#1d6b66" />
        <rect x="16" y="188" width="68" height="32" rx="8" fill="#7ee0d8" />
        <rect x="16" y="188" width="68" height="12" rx="6" fill="#e7fffb" opacity="0.8" />
        <text x="274" y="44" fill="#efeef7" fontSize="16" fontFamily="system-ui, sans-serif">42%</text>
        <text x="194" y="100" fill="#efeef7" fontSize="16" fontFamily="system-ui, sans-serif">28%</text>
        <text x="138" y="156" fill="#efeef7" fontSize="16" fontFamily="system-ui, sans-serif">18%</text>
        <text x="94" y="212" fill="#efeef7" fontSize="16" fontFamily="system-ui, sans-serif">12%</text>
      </svg>
    </figure>
  )
}

function BandsGraphic() {
  return (
    <figure className="welcome-graphic">
      <svg viewBox="0 0 320 240" role="img" aria-labelledby="bands-graphic-title">
        <title id="bands-graphic-title">Bars, a short summary, then posts</title>
        <rect x="28" y="8" width="264" height="224" rx="22" fill="#0c0e16" stroke="rgba(239,238,247,0.2)" />
        <rect x="44" y="24" width="232" height="58" rx="10" fill="#161a28" stroke="rgba(244,193,78,0.7)" />
        <rect x="58" y="40" width="120" height="26" rx="6" fill="#f4c14e" />
        <rect x="186" y="40" width="70" height="26" rx="6" fill="#4aa3e6" />
        <rect x="44" y="94" width="232" height="58" rx="10" fill="#12151f" stroke="rgba(239,238,247,0.16)" />
        <rect x="58" y="112" width="170" height="8" rx="3" fill="rgba(239,238,247,0.82)" />
        <rect x="58" y="128" width="124" height="8" rx="3" fill="rgba(239,238,247,0.4)" />
        <rect x="44" y="164" width="232" height="52" rx="10" fill="#10131c" stroke="rgba(239,238,247,0.1)" />
        <rect x="58" y="180" width="190" height="7" rx="3" fill="rgba(239,238,247,0.32)" />
        <rect x="58" y="196" width="146" height="7" rx="3" fill="rgba(239,238,247,0.16)" />
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
            <BarsGraphic />
            <BandsGraphic />
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
