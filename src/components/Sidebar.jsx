import { useLayoutEffect, useRef } from 'react'
import { categoryCounts } from '../lib/categories'
import { SITE_TAGLINE } from '../lib/copy'
import { faceShade, hexToRgba, rankPerspectives, topicColor } from '../lib/colors'
import { formatNumber, formatPercent } from '../lib/layout'
import { LazyPostFeed, TopTerms } from './FaceEvidence'
import MiniCube from './MiniCube'
import TopicFilter from './TopicFilter'

function VolumeBar({ value, color, active = false }) {
  return (
    <div className={`volume-bar ${active ? 'is-active' : ''}`}>
      <span className="volume-bar-track">
        <span
          className="volume-bar-fill"
          style={{ width: `${Math.max(value, 2.5)}%`, background: color }}
        />
      </span>
      <span className="volume-bar-value">{formatPercent(value)}</span>
    </div>
  )
}

function FilterStrip({ categories, category, counts, onCategory }) {
  return (
    <div className="filter-strip">
      <TopicFilter
        id="sidebar-topic-filter"
        categories={categories}
        category={category}
        counts={counts}
        onCategory={onCategory}
      />
    </div>
  )
}

function WelcomePanel({
  data,
  topics,
  isMobile,
  onSelectTopic,
  categories,
  category,
  counts,
  onCategory,
}) {
  if (isMobile) {
    return (
      <div className="panel is-mobile-home">
        <TopicFilter
          id="mobile-topic-filter"
          categories={categories}
          category={category}
          counts={counts}
          onCategory={onCategory}
        />
        <p className="mobile-prompt">
          Drag the solar system to look around. Bigger planets are what more people talked
          about this week. Tap one to open its opinions — the longest bar
          is the most common view.
        </p>
        <div className="planet-rail" aria-label="Today's planets">
          {topics.map((topic) => (
            <button
              key={topic.id}
              type="button"
              className="planet-chip"
              onClick={() => onSelectTopic(topic.id)}
            >
              <span className="swatch" style={{ background: topicColor(topic.id, topic.body) }} />
              <span>
                {topic.name}
                <small>{formatPercent(topic.total_volume_percent)} of attention</small>
              </span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <p className="eyebrow">This week&apos;s map</p>
      <h1>Perspectiverse</h1>
      <p className="tagline">{SITE_TAGLINE}</p>
      {data.mode === 'demo' && (
        <p className="demo-banner">
          Demo data. These posts are a made-up example, not a live feed.
        </p>
      )}
      <p className="lede">
        A week of public conversation as a solar system. Bigger planets got more
        attention. Open one to see the main opinions — the longest bar
        is the most common view, and shorter bars are smaller views. That is
        where yours stacks up.
      </p>
      <div className="stat-grid">
        <div>
          <strong>{formatNumber(data.total_posts)}</strong>
          <span>posts this week</span>
        </div>
        <div>
          <strong>{topics.length}</strong>
          <span>planets in view</span>
        </div>
        <div>
          <strong>{data.last_updated}</strong>
          <span>updated</span>
        </div>
      </div>
      <div className="topic-list">
        <h2>Today&apos;s planets</h2>
        {topics.map((topic, index) => (
          <button
            key={topic.id}
            type="button"
            className="topic-row"
            onClick={() => onSelectTopic(topic.id)}
          >
            <span className="swatch" style={{ background: topicColor(topic.id, topic.body) }} />
            <span className="topic-row-copy">
              <span className="topic-row-name">
                {topic.body?.name ?? (index === 0 ? 'Sun' : `Orbit ${index}`)} · {topic.name}
              </span>
              <span className="topic-row-meta">
                {topic.category} · {topic.perspectives.length} views
              </span>
            </span>
            <VolumeBar value={topic.total_volume_percent} color={topicColor(topic.id, topic.body)} />
          </button>
        ))}
      </div>
    </div>
  )
}

function EmptyCategory({ category, onShowAll }) {
  return (
    <div className="panel">
      <p className="eyebrow">Empty solar system</p>
      <h1>Nothing in {category}</h1>
      <p className="lede">
        This snapshot has no {category} topics. The solar system is empty on purpose.
        Choose another filter, or show everything.
      </p>
      <button type="button" className="back-link" onClick={onShowAll}>
        Show all topics
      </button>
    </div>
  )
}

function TopicPanel({
  topic,
  selectedPerspectiveId,
  isMobile,
  onSelectPerspective,
  onBack,
}) {
  const color = topicColor(topic.id, topic.body)
  const ranked = rankPerspectives(topic.perspectives)
  return (
    <div className="panel is-topic">
      <button type="button" className="back-link" onClick={onBack}>
        {isMobile ? '← Back to the solar system' : '← All topics'}
      </button>
      <p className="eyebrow" style={{ color }}>
        {topic.body?.name} · {topic.category} · {topic.perspectives.length} views
      </p>
      <h1>{topic.name}</h1>
      <p className="lede">
        This planet is {formatPercent(topic.total_volume_percent)} of the attention
        among the planets in view — those shares always add up to 100%. That is
        attention, not importance. Each bar below is a real opinion. Length shows
        how many posts sat there. A longer bar is the more common view.
      </p>
      {ranked.length === 1 && (
        <p className="lede">{topic.opposing_note || 'No clear opposing view found in this sample'}</p>
      )}
      <MiniCube
        topic={topic}
        selectedPerspectiveId={selectedPerspectiveId}
        onSelectPerspective={onSelectPerspective}
      />
      <div className="perspective-list">
        <h2>Opinions</h2>
        {ranked.map((perspective) => {
          const tint = faceShade(color, ranked.indexOf(perspective), ranked.length)
          return (
            <button
              key={perspective.id}
              type="button"
              className={`perspective-card ${selectedPerspectiveId === perspective.id ? 'is-active' : ''}`}
              onClick={() => onSelectPerspective(perspective.id)}
            >
              <div className="perspective-card-head">
                <span className="swatch" style={{ background: tint, boxShadow: `0 0 12px ${tint}` }} />
                <div>
                  <h3>{perspective.title}</h3>
                  <p>{perspective.summary}</p>
                </div>
              </div>
              <VolumeBar
                value={perspective.volume_percent}
                color={tint}
                active={selectedPerspectiveId === perspective.id}
              />
              <span className="card-chevron" aria-hidden="true">›</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function PerspectivePanel({
  topic,
  perspective,
  onBack,
}) {
  const planetColor = topicColor(topic.id, topic.body)
  const ranked = rankPerspectives(topic.perspectives)
  const color = faceShade(planetColor, ranked.findIndex((item) => item.id === perspective.id), ranked.length)
  const argumentsList = (perspective.arguments ?? []).filter((item) => String(item).trim())

  return (
    <div className="panel is-face">
      <button type="button" className="back-link" onClick={onBack}>
        ← Back to {topic.name}
      </button>
      <p className="eyebrow" style={{ color }}>
        {topic.body?.name} · {topic.name}
      </p>
      <h1>{perspective.title}</h1>
      <p className="lede">{perspective.summary}</p>
      <TopTerms terms={perspective.top_terms} />
      <MiniCube topic={topic} selectedPerspectiveId={perspective.id} />
      {argumentsList.length > 0 && (
        <section className="argument-card">
          <h2>Core arguments</h2>
          <p className="topic-row-meta">
            The strongest version of what these posts are saying.
          </p>
          <ul>
            {argumentsList.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}
      <div
        className="perspective-stat"
        style={{ borderColor: hexToRgba(planetColor, 0.4), background: hexToRgba(planetColor, 0.08) }}
      >
        {ranked.length === 1 ? (
          <>
            <strong>One view</strong>
            <span>{topic.opposing_note || 'No clear opposing view found in this sample'}</span>
          </>
        ) : (
          <>
            <strong>{formatPercent(perspective.volume_percent)}</strong>
            <span>of this planet&apos;s conversation — longest if this is the most common view, shorter if fewer posts sat here</span>
          </>
        )}
      </div>
      <div className="post-feed">
        <h2>Example posts</h2>
        <p className="topic-row-meta">Posts from this view, sorted by likes — the talk behind the summary.</p>
        <LazyPostFeed posts={perspective.representative_posts} faceKey={perspective.id} />
      </div>
    </div>
  )
}

export default function Sidebar({
  data,
  topics,
  categories,
  category,
  selectedTopic,
  selectedPerspective,
  isMobile,
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
  onCategory,
}) {
  const counts = categoryCounts(data.topics)
  const empty = topics.length === 0
  const scroller = useRef(null)

  useLayoutEffect(() => {
    if (scroller.current) scroller.current.scrollTop = 0
    window.scrollTo(0, 0)
    document.documentElement.scrollTop = 0
  }, [selectedTopic?.id, selectedPerspective?.id, category])

  return (
    <aside
      ref={scroller}
      className="sidebar"
      key={`${selectedTopic?.id ?? 'home'}-${selectedPerspective?.id ?? 'list'}-${category}`}
    >
      {!isMobile && (
        <FilterStrip
          categories={categories}
          category={category}
          counts={counts}
          onCategory={onCategory}
        />
      )}
      {empty && <EmptyCategory category={category} onShowAll={() => onCategory('all')} />}
      {!empty && !selectedTopic && (
        <WelcomePanel
          data={data}
          topics={topics}
          isMobile={isMobile}
          onSelectTopic={onSelectTopic}
          categories={categories}
          category={category}
          counts={counts}
          onCategory={onCategory}
        />
      )}
      {!empty && selectedTopic && !selectedPerspective && (
        <TopicPanel
          topic={selectedTopic}
          selectedPerspectiveId={null}
          isMobile={isMobile}
          onSelectPerspective={onSelectPerspective}
          onBack={onClearSelection}
        />
      )}
      {!empty && selectedTopic && selectedPerspective && (
        <PerspectivePanel
          topic={selectedTopic}
          perspective={selectedPerspective}
          isMobile={isMobile}
          onBack={() => onSelectPerspective(null)}
        />
      )}
    </aside>
  )
}
