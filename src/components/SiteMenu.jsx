import { useEffect, useRef } from 'react'
import { hexToRgba } from '../lib/colors'
import { formatPercent } from '../lib/layout'
import PerspectiverseGraphic from './PerspectiverseGraphic'
import SkySelect from './SkySelect'

const FEEDBACK_URL =
  'https://github.com/Data-Science-Link/perspectiverse/issues/new?title=Feedback'

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  )
}

export default function SiteMenu({
  open,
  data,
  topics,
  categories,
  category,
  counts,
  onClose,
  onCategory,
  onSelectTopic,
}) {
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const previous = document.activeElement
    closeRef.current?.focus()
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = original
      if (previous instanceof HTMLElement) previous.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="menu-layer">
      <aside className="menu-drawer" role="dialog" aria-modal="true" aria-labelledby="menu-title">
        <div className="menu-head">
          <div>
            <p className="eyebrow">Menu</p>
            <h2 id="menu-title">Perspectiverse</h2>
          </div>
          <button ref={closeRef} type="button" className="icon-btn" onClick={onClose} aria-label="Close menu">
            <CloseIcon />
          </button>
        </div>

        <section className="menu-section">
          <h3>The graphic</h3>
          <PerspectiverseGraphic />
        </section>

        <section className="menu-section">
          <h3>About the project</h3>
          <p>
            A week of public conversation, mapped as a solar system. The largest topic sits at
            the center as the sun. The next nine orbit by volume and wear Mercury through Pluto
            in that order. Size is share of attention. Open a planet and the sphere dissolves
            into a crystal of two to six faces. Gold is the loudest perspective, then ember,
            sky, violet, jade, and rose.
          </p>
          <p>
            Source: {data.mode === 'demo' || data.source === 'synthetic'
              ? 'a synthetic demo sky, not a live feed'
              : data.source === 'bluesky'
                ? 'public English posts on Bluesky'
                : 'the snapshot bundled with this page'}.
            Window: the last {data.window_hours ?? 168} hours. Snapshot {data.last_updated}.
          </p>
        </section>

        <section className="menu-section">
          <h3>How to read this</h3>
          <ul>
            <li>On a phone, tap a planet. The page jumps to that topic and the sphere becomes geometry.</li>
            <li>On a desktop, drag to orbit, then click a planet to dissolve it into its crystal.</li>
            <li>The longest face is louder because more posts clustered there, not because it is truer.</li>
            <li>Test your take against the snapshot. A claim, a brand, or a question — you may be the sun, a minority spike, or not on the sky at all.</li>
          </ul>
        </section>

        <section className="menu-section">
          <h3>What this is not</h3>
          <ul>
            <li>Internet discourse, not a poll of humanity. Bluesky is not everyone.</li>
            <li>A face summary collapses dissent inside that cluster.</li>
            <li>Posts that fit no planet are left out of the percentages.</li>
          </ul>
        </section>

        <section className="menu-section">
          <h3>Filter the sky</h3>
          <SkySelect
            id="menu-sky-select"
            categories={categories}
            category={category}
            counts={counts}
            onCategory={(next) => {
              onCategory(next)
              onClose()
            }}
          />
        </section>

        <section className="menu-section">
          <h3>Today&apos;s planets</h3>
          <div className="menu-planets">
            {topics.map((topic) => (
              <button
                key={topic.id}
                type="button"
                className="menu-planet"
                onClick={() => {
                  onSelectTopic(topic.id)
                  onClose()
                }}
              >
                <span className="swatch" style={{ background: topic.body?.color, boxShadow: `0 0 12px ${hexToRgba(topic.body?.color ?? '#fff', 0.5)}` }} />
                <span>
                  <strong>{topic.body?.name}</strong>
                  <em>{topic.name}</em>
                </span>
                <span>{formatPercent(topic.total_volume_percent)}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="menu-section">
          <h3>Feedback</h3>
          <p>
            Something confusing, a planet that feels wrong, a face that flattened you? This is
            a research prototype and we want the seams.
          </p>
          <a className="menu-feedback" href={FEEDBACK_URL} target="_blank" rel="noreferrer">
            Open a GitHub issue
          </a>
        </section>
      </aside>
      <button type="button" className="menu-backdrop" aria-label="Close menu" onClick={onClose} />
    </div>
  )
}
