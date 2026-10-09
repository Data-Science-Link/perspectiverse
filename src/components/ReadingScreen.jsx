import { useEffect, useMemo, useState } from 'react'
import { formatNumber, formatPercent, sortPosts } from '../lib/layout'
import BarChart from './BarChart'
import { LazyPostFeed, POST_PREVIEW_COUNT, TopTerms } from './FaceEvidence'

function paragraphs(text) {
  return String(text || '')
    .split(/\n\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
}

function examplePosts(topic, perspective) {
  if (perspective) return sortPosts(perspective.representative_posts || [])
  const posts = []
  const seen = new Set()
  for (const face of topic?.perspectives || []) {
    for (const post of face.representative_posts || []) {
      const key = `${post.author}\n${post.text}`
      if (seen.has(key)) continue
      seen.add(key)
      posts.push(post)
    }
  }
  return sortPosts(posts)
}

function emailPlain(digest, updated) {
  const lines = [
    'From: Perspectiverse',
    `Date: ${updated || 'this week'}`,
    `Subject: ${digest?.subject || 'This week'}`,
    '',
  ]
  for (const planet of digest?.planets || []) {
    lines.push(planet.name || 'Planet')
    if (planet.percent != null) lines.push(formatPercent(planet.percent))
    for (const argument of planet.arguments || []) lines.push(`• ${argument}`)
    if (planet.disagreement) lines.push(planet.disagreement)
    lines.push('')
  }
  return lines.join('\n')
}

function argumentGroups(items) {
  const groups = []
  for (const item of items || []) {
    const splitAt = item.indexOf(': ')
    const titled = splitAt > 0 && splitAt <= 42
    const title = titled ? item.slice(0, splitAt) : ''
    const text = titled ? item.slice(splitAt + 2) : item
    const last = groups[groups.length - 1]
    if (last && last.title === title) last.lines.push(text)
    else groups.push({ title, lines: [text] })
  }
  return groups
}

function EmailView({ data, onClose }) {
  const digest = data?.digest
  const [copied, setCopied] = useState(false)
  const plain = useMemo(() => emailPlain(digest, data?.last_updated), [digest, data?.last_updated])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(plain)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className="email-sheet" aria-label="Weekly email">
      <header className="email-head">
        <p className="eyebrow">Email</p>
        <h1>{digest?.subject || 'This week'}</h1>
        <p className="email-meta">
          Perspectiverse
          {data?.last_updated ? ` · ${data.last_updated}` : ''}
        </p>
        <div className="reading-actions">
          <button type="button" className="text-button" onClick={copy}>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" className="text-button" onClick={onClose}>
            Close
          </button>
        </div>
      </header>
      <div className="email-body">
        {(digest?.planets || []).map((planet) => (
          <section key={planet.name} className="email-planet">
            <h2>
              {planet.name}
              {planet.percent != null && <span>{formatPercent(planet.percent)}</span>}
            </h2>
            {planet.category && <p className="email-category">{planet.category}</p>}
            {argumentGroups(planet.arguments).map((group) => (
              <div key={`${planet.name}-${group.title || 'claim'}`} className="email-side">
                {group.title && <h3>{group.title}</h3>}
                <ul>
                  {group.lines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>
            ))}
            {planet.disagreement && <p className="email-disagreement">{planet.disagreement}</p>}
          </section>
        ))}
        {!digest?.planets?.length && <p>No planets in this snapshot.</p>}
      </div>
    </article>
  )
}

export default function ReadingScreen({
  data,
  topics,
  category,
  selectedTopic,
  selectedPerspective,
  highlightedTopicId,
  isMobile,
  emailOpen,
  onOpenTopic,
  onSelectPerspective,
  onBack,
  onCategory,
  onToggleEmail,
}) {
  const [expanded, setExpanded] = useState(false)
  const [sheet, setSheet] = useState(null)
  const highlighted = topics.find((topic) => topic.id === highlightedTopicId) ?? topics[0] ?? null
  const topic = selectedTopic
  const perspective = selectedPerspective
  const depth = topic ? 'planet' : 'system'

  const bars = useMemo(() => {
    if (topic) {
      return (topic.perspectives || []).map((face) => ({
        id: face.id,
        label: face.title,
        value: face.volume_percent,
        color: topic.body?.color,
        textureKey: topic.body?.key,
      }))
    }
    return topics.map((item) => ({
      id: item.id,
      label: item.name,
      value: item.total_volume_percent,
      color: item.body?.color,
      textureKey: item.body?.key,
    }))
  }, [topic, topics])

  const selectedId = topic ? perspective?.id ?? null : highlighted?.id ?? null
  const subject = topic ? (perspective || topic) : highlighted
  const title = perspective?.title || topic?.name || highlighted?.name || 'This week'
  const brief = subject?.brief || subject?.summary || ''
  const detail = subject?.detail || brief
  const posts = examplePosts(topic || highlighted, perspective)
  const countSubject = perspective || topic || highlighted
  const postCount = countSubject?.post_count ?? data?.total_posts ?? 0
  const selectionKey = `${depth}:${topic?.id ?? 'system'}:${perspective?.id ?? 'planet'}:${highlighted?.id ?? ''}`

  useEffect(() => {
    setExpanded(false)
    setSheet(null)
  }, [selectionKey])

  const mobilePlanet = Boolean(isMobile && topic)
  const faceTerms = perspective?.top_terms

  const openSummary = () => {
    if (mobilePlanet) {
      setSheet('summary')
      return
    }
    setExpanded((value) => !value)
  }

  const chooseBar = (id) => {
    if (topic) {
      onSelectPerspective(id)
      return
    }
    onOpenTopic(id)
  }

  if (emailOpen) {
    return (
      <section className="reading-screen" aria-label="This week">
        <EmailView data={data} onClose={onToggleEmail} />
      </section>
    )
  }

  return (
    <section className={`reading-screen ${sheet ? 'is-sheet' : ''}`} aria-label="This week">
      <header className="reading-toolbar">
        {sheet ? (
          <button type="button" className="back-link" onClick={() => setSheet(null)}>
            ← Back to the planet
          </button>
        ) : topic ? (
          <button type="button" className="back-link" onClick={onBack}>
            {isMobile ? '← Back to the solar system' : '← All topics'}
          </button>
        ) : null}
        <div className="reading-actions" aria-hidden="true" />
      </header>
      {sheet === 'summary' && (
        <div className="reading-sheet">
          <p className="eyebrow">
            {perspective ? topic.name : topic.category}
            {postCount ? ` · ${formatNumber(postCount)} posts` : ''}
          </p>
          <h1>{title}</h1>
          {brief && <p className="reading-brief">{brief}</p>}
          <div className="reading-detail">
            {paragraphs(detail).map((part) => (
              <p key={part} className={part.includes('“') ? 'is-quote' : undefined}>
                {part}
              </p>
            ))}
          </div>
        </div>
      )}
      {sheet === 'posts' && (
        <div className="reading-sheet">
          <h1>Example posts</h1>
          <div className="reading-sheet-posts">
            <TopTerms terms={faceTerms} />
            <LazyPostFeed posts={posts} faceKey={selectionKey} />
          </div>
        </div>
      )}
      {!sheet && (topics.length === 0 ? (
        <div className="reading-empty">
          <h1>Nothing in {category}</h1>
          <button type="button" className="text-button" onClick={() => onCategory('all')}>
            All topics
          </button>
        </div>
      ) : (
        <div className="reading-body">
          <div className="reading-band">
            <BarChart bars={bars} selectedId={selectedId} onSelect={chooseBar} />
          </div>
          <div className="reading-band reading-copy">
            <p className="eyebrow">
              {perspective ? topic.name : topic ? topic.category : highlighted?.category}
              {postCount ? ` · ${formatNumber(postCount)} posts` : ''}
            </p>
            <h1>{title}</h1>
            {topic && topic.perspectives.length === 1 && (
              <p className="reading-opposing">
                {topic.opposing_note || 'No clear opposing view found in this sample'}
              </p>
            )}
            {brief && <p className="reading-brief">{brief}</p>}
            {topic && perspective && <TopTerms terms={faceTerms} />}
            <div className="reading-actions">
              <button type="button" className="text-button" onClick={openSummary}>
                {expanded && !mobilePlanet ? 'Show less' : 'Read more …'}
              </button>
              {!topic && highlighted && (
                <button type="button" className="text-button is-strong" onClick={() => onOpenTopic(highlighted.id)}>
                  Perspectives
                </button>
              )}
            </div>
            {expanded && (
              <div className="reading-detail">
                {paragraphs(detail).map((part) => (
                  <p key={part} className={part.includes('“') ? 'is-quote' : undefined}>
                    {part}
                  </p>
                ))}
              </div>
            )}
          </div>
          <div className="reading-band reading-posts">
            <div className="posts-head">
              <h2>Example posts</h2>
              {mobilePlanet && posts.length > 0 && (
                <button type="button" className="text-button" onClick={() => setSheet('posts')}>
                  See all posts
                </button>
              )}
            </div>
            <div className="post-scroller">
              <LazyPostFeed
                posts={posts}
                previewCount={POST_PREVIEW_COUNT}
                faceKey={selectionKey}
              />
            </div>
          </div>
        </div>
      ))}
    </section>
  )
}
