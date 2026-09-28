import { useCallback, useEffect, useRef, useState } from 'react'
import { SITE_TAGLINE, setWelcomeHidden } from '../lib/copy'

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
            This is a map of a week of public conversation — not your feed. Tilt the
            sky so you can see <strong>every</strong> perspective, then check where
            yours stacks up. The point is to step out of an echo chamber: is the topic
            you care about actually of interest to the general public, and are you the
            majority or a minority opinion?
          </p>

          <section>
            <h3>What to do</h3>
            <ol>
              <li>Drag, pinch, or tilt to orbit. Every planet keeps turning on its own axis so all sides come into view.</li>
              <li>Tap a planet. The sphere dissolves into geometry — that is the conversation, split into real views.</li>
              <li>Tap a face to read the posts behind it. Gold is the loudest view, not the truest one.</li>
            </ol>
          </section>

          <section>
            <h3>Planet size</h3>
            <p>
              Size is share of attention that week. A large planet means many people
              were talking about it. A small one means your interest may be a niche —
              still real, just not the public&apos;s main object.
            </p>
          </section>

          <section>
            <h3>The crystal</h3>
            <p>
              Clicking in opens two to six faces. Face length is how much of that
              topic sits in that view. The long gold face is the majority. Shorter
              faces are minority opinions. Turn it until you see whether your take is
              the sun, a spike, or missing from this sky.
            </p>
          </section>
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
            Enter the sky
          </button>
        </footer>
      </aside>
      <button type="button" className="welcome-backdrop" aria-label="Close welcome" onClick={dismiss} />
    </div>
  )
}
