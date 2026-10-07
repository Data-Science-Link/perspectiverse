import { useCallback, useEffect, useRef, useState } from 'react'
import { SITE_TAGLINE, setWelcomeHidden } from '../lib/copy'
import WelcomeHowItWorks from './WelcomeHowItWorks'

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
          <WelcomeHowItWorks />
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
