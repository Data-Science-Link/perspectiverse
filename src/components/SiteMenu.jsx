import { useEffect, useRef } from 'react'
import { hexToRgba } from '../lib/colors'
import { formatPercent } from '../lib/layout'
import PerspectiverseGraphic from './PerspectiverseGraphic'

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
      <button type="button" className="menu-backdrop" aria-label="Close menu" onClick={onClose} />
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
            in that order. Each body still grows six spikes — the dominant perspectives inside
            that topic.
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
            <li>On a phone, tap a cube. The page jumps to that topic.</li>
            <li>On a desktop, drag to orbit, scroll to zoom, click a planet to inspect it.</li>
            <li>A long spike is louder because more posts clustered there, not because it is truer.</li>
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
          <div className="filter-strip is-menu" role="tablist" aria-label="Category">
            <button
              type="button"
              className={`filter-chip ${category === 'all' ? 'is-active' : ''}`}
              onClick={() => {
                onCategory('all')
                onClose()
              }}
            >
              All
            </button>
            {categories.map((name) => (
              <button
                key={name}
                type="button"
                className={`filter-chip ${category === name ? 'is-active' : ''}`}
                onClick={() => {
                  onCategory(name)
                  onClose()
                }}
              >
                {name}
                <span className="filter-count">{counts[name] ?? 0}</span>
              </button>
            ))}
          </div>
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
    </div>
  )
}
