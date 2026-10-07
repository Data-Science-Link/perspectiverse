import { useEffect, useRef } from 'react'
import { SITE_TAGLINE } from '../lib/copy'
import { FEEDBACK_URL, SITE_PAGES } from '../lib/pages'
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
  categories,
  category,
  counts,
  currentPage = null,
  onClose,
  onCategory,
  onOpenPage,
  onShowWelcome,
  onOpenEmail,
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
            <p className="menu-tagline">{SITE_TAGLINE}</p>
          </div>
          <button ref={closeRef} type="button" className="icon-btn" onClick={onClose} aria-label="Close menu">
            <CloseIcon />
          </button>
        </div>

        <section className="menu-section menu-section-tight">
          <button
            type="button"
            className="menu-email-cta"
            onClick={() => {
              onOpenEmail?.()
              onClose()
            }}
          >
            <strong>Weekly email digest</strong>
            <span>Copy this week&apos;s planets and perspectives</span>
          </button>
        </section>

        <section className="menu-section">
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
          {onShowWelcome && (
            <button type="button" className="menu-inline-link" onClick={onShowWelcome}>
              How it works (welcome tour)
            </button>
          )}
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

        <section className="menu-section menu-section-tight">
          <a className="menu-feedback" href={FEEDBACK_URL} target="_blank" rel="noreferrer">
            Feedback on GitHub
          </a>
        </section>
      </aside>
    </div>
  )
}
