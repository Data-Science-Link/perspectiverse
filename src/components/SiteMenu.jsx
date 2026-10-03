import { useEffect, useRef } from 'react'
import { SITE_TAGLINE } from '../lib/copy'
import { FEEDBACK_URL, SITE_PAGES } from '../lib/pages'
import { hexToRgba } from '../lib/colors'
import { formatPercent } from '../lib/layout'
import TopicFilter from './TopicFilter'

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg className="menu-page-chevron" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

export default function SiteMenu({
  open,
  topics,
  categories,
  category,
  counts,
  currentPage = null,
  onClose,
  onCategory,
  onSelectTopic,
  onOpenPage,
  onShowWelcome,
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
            <p className="menu-tagline">{SITE_TAGLINE}</p>
          </div>
          <button ref={closeRef} type="button" className="icon-btn" onClick={onClose} aria-label="Close menu">
            <CloseIcon />
          </button>
        </div>

        <section className="menu-section">
          <h3>Pages</h3>
          <nav className="menu-pages" aria-label="Site pages">
            {SITE_PAGES.map((page) => (
              <button
                key={page.id}
                type="button"
                className={`menu-page ${currentPage === page.id ? 'is-current' : ''}`}
                aria-current={currentPage === page.id ? 'page' : undefined}
                onClick={() => onOpenPage(page.id)}
              >
                <span>
                  <strong>{page.menuLabel}</strong>
                  <em>{page.subtitle}</em>
                </span>
                <ChevronIcon />
              </button>
            ))}
          </nav>
        </section>

        <section className="menu-section">
          <h3>About the project</h3>
          <p>
            A week of public conversation as a solar system. The briefing beside it
            is the same at every depth: bars, a summary, and posts.
          </p>
          {onShowWelcome && (
            <button type="button" className="menu-feedback" onClick={onShowWelcome}>
              Show the welcome tour
            </button>
          )}
        </section>

        <section className="menu-section">
          <h3>How to read this</h3>
          <ul>
            <li>Drag to look around the planets.</li>
            <li>Tap a bar to read that planet or perspective.</li>
            <li>Read more opens the longer summary. Example posts sit underneath.</li>
          </ul>
        </section>

        <section className="menu-section">
          <h3>Filter topics</h3>
          <TopicFilter
            id="menu-topic-filter"
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
            Something confusing, a planet that feels wrong, or a view that flattened
            your take? This is a research prototype — tell us.
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
