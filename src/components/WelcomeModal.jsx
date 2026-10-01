import { useCallback, useEffect, useRef, useState } from 'react'
import { SITE_TAGLINE, setWelcomeHidden } from '../lib/copy'

function SizeGraphic() {
  return (
    <figure className="welcome-graphic">
      <h3>Planet size</h3>
      <svg viewBox="0 0 320 118" role="img" aria-labelledby="size-graphic-title">
        <title id="size-graphic-title">A large planet means more public attention than a small one</title>
        <circle cx="160" cy="58" r="52" fill="none" stroke="rgba(215,222,245,0.12)" />
        <circle cx="160" cy="58" r="34" fill="none" stroke="rgba(215,222,245,0.08)" />
        <circle cx="78" cy="60" r="38" fill="#f4c14e" />
        <circle cx="78" cy="48" r="14" fill="rgba(255,255,255,0.18)" />
        <text x="78" y="108" textAnchor="middle" fill="#efeef7" fontSize="12">More talk</text>
        <circle cx="236" cy="74" r="16" fill="#4aa3e6" />
        <circle cx="230" cy="68" r="5" fill="rgba(255,255,255,0.22)" />
        <text x="236" y="108" textAnchor="middle" fill="#efeef7" fontSize="12">Niche</text>
      </svg>
      <figcaption>Bigger planets got more public attention this week. Small is still real — just not the main story.</figcaption>
    </figure>
  )
}

function CrystalGraphic() {
  return (
    <figure className="welcome-graphic">
      <h3>The views inside</h3>
      <svg viewBox="0 0 320 118" role="img" aria-labelledby="crystal-graphic-title">
        <title id="crystal-graphic-title">A planet opens into a cube. The longest, most solid spike is the majority view</title>
        <circle cx="58" cy="56" r="26" fill="#7ee0d8" />
        <circle cx="48" cy="46" r="9" fill="rgba(255,255,255,0.2)" />
        <text x="58" y="108" textAnchor="middle" fill="#efeef7" fontSize="12">Planet</text>
        <path d="M96 56 H132" stroke="rgba(239,238,247,0.55)" strokeWidth="2" />
        <path d="M124 50 L134 56 L124 62" fill="none" stroke="rgba(239,238,247,0.55)" strokeWidth="2" />
        <polygon points="176,34 244,34 244,78 176,78" fill="#1a3d3c" stroke="rgba(126,224,216,0.7)" />
        <polygon points="210,18 226,40 194,40" fill="#7ee0d8" />
        <polygon points="244,40 262,56 244,72" fill="rgba(126,224,216,0.55)" />
        <polygon points="194,78 226,78 210,96" fill="rgba(126,224,216,0.32)" />
        <text x="210" y="108" textAnchor="middle" fill="#efeef7" fontSize="12">Opinions</text>
        <text x="268" y="22" fill="#7ee0d8" fontSize="11">Majority</text>
      </svg>
      <figcaption>Tap a planet and it opens into a cube with two to six spikes. The longest, most solid spike is the majority — loudest, not truest.</figcaption>
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
          <p className="eyebrow">Welcome</p>
          <h2 id="welcome-title">Perspectiverse</h2>
          <p className="welcome-tagline">{SITE_TAGLINE}</p>
        </header>
        <div className="welcome-body">
          <p>
            A week of public conversation as a solar system — not your feed. Step out of an
            echo chamber: is this topic widely discussed, and are you the majority or a minority?
          </p>

          <section>
            <h3>What to do</h3>
            <ol>
              <li>Drag, pinch, or tilt to look around. Planets keep turning so every side comes into view.</li>
              <li>Tap a planet to open its opinions, then tap a face to read its core arguments and posts.</li>
              <li>Use <strong>Filter topics</strong> to open a newspaper section — World, Politics, Business, Technology, Sports, and the rest. All topics stays the week&rsquo;s largest planets.</li>
            </ol>
          </section>

          <div className="welcome-graphics">
            <SizeGraphic />
            <CrystalGraphic />
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
