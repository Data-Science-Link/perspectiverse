import { useLayoutEffect, useRef } from 'react'
import { shapeName } from '../lib/faces'
import { categoryCounts } from '../lib/categories'
import { hexToRgba, rankPerspectives, spikeColor, topicColor } from '../lib/colors'
import { formatNumber, formatPercent, sortPosts, topicScale } from '../lib/layout'
import MiniCube from './MiniCube'
import PerspectiverseGraphic from './PerspectiverseGraphic'
import EngagementPanel from './EngagementPanel'
import SkySelect from './SkySelect'

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
      <SkySelect
        id="sidebar-sky-select"
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
  onSelectLocation,
  engagementQuery,
  onEngagementQuery,
  categories,
  category,
  counts,
  onCategory,
}) {
  if (isMobile) {
    return (
      <div className="panel is-mobile-home">
        <SkySelect
          id="mobile-sky-select"
          categories={categories}
          category={category}
          counts={counts}
          onCategory={onCategory}
        />
        <PerspectiverseGraphic compact />
        <p className="mobile-prompt">Tap a cube to open its topic.</p>
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
                {topic.body?.name}
                <small>{topic.name}</small>
              </span>
            </button>
          ))}
        </div>
        <EngagementPanel
          topics={topics}
          query={engagementQuery}
          onQueryChange={onEngagementQuery}
          onSelectTopic={onSelectTopic}
          onSelectPerspective={(faceId) => {
            const host = topics.find((item) => item.perspectives.some((face) => face.id === faceId))
            if (host) onSelectLocation({ topicId: host.id, perspectiveId: faceId })
          }}
          onSelectLocation={onSelectLocation}
          compact
        />
      </div>
    )
  }

  return (
    <div className="panel">
      <p className="eyebrow">Discourse Universe</p>
      <h1>Perspectiverse</h1>
      {data.mode === 'demo' && (
        <p className="demo-banner">
          Synthetic demo sky. These posts were written as a fixture, not pulled from a live feed.
        </p>
      )}
      <p className="lede">
        A gravitational map of a week of public conversation. The largest topic is the sun.
        The rest orbit by volume and wear Mercury through Pluto in that order. Open a planet
        and the sphere dissolves into a crystal of two to six faces — one per real
        perspective, never more than a cube. Gold is always the loudest view.
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
          <span>snapshot</span>
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
                {topic.category} · {shapeName(topic.perspectives.length)} ·{' '}
                {topic.perspectives.length} perspectives
              </span>
            </span>
            <VolumeBar value={topic.total_volume_percent} color={topicColor(topic.id, topic.body)} />
          </button>
        ))}
      </div>
      <EngagementPanel
        topics={topics}
        query={engagementQuery}
        onQueryChange={onEngagementQuery}
        onSelectTopic={onSelectTopic}
        onSelectPerspective={(faceId) => {
          const host = topics.find((item) => item.perspectives.some((face) => face.id === faceId))
          if (host) onSelectLocation({ topicId: host.id, perspectiveId: faceId })
        }}
        onSelectLocation={onSelectLocation}
      />
    </div>
  )
}

function EmptyCategory({ category, onShowAll }) {
  return (
    <div className="panel">
      <p className="eyebrow">Empty sky</p>
      <h1>Nothing in {category}</h1>
      <p className="lede">
        This snapshot has no planets tagged {category}. The canvas stays up so the view is empty
        on purpose, not broken.
      </p>
      <button type="button" className="back-link" onClick={onShowAll}>
        Show all topics
      </button>
    </div>
  )
}

function TopicPanel({
  topic,
  topics,
  selectedPerspectiveId,
  isMobile,
  onSelectPerspective,
  onBack,
  engagementQuery,
  onEngagementQuery,
  onSelectTopic,
  volumeMax = 100,
}) {
  const color = topicColor(topic.id, topic.body)
  const ranked = rankPerspectives(topic.perspectives)
  return (
    <div className="panel is-topic">
      {!isMobile && (
        <button type="button" className="back-link" onClick={onBack}>
          ← All topics
        </button>
      )}
      <p className="eyebrow" style={{ color }}>
        {topic.body?.name} · {shapeName(topic.perspectives.length)} · {topic.category}
      </p>
      <h1>{topic.name}</h1>
      <p className="lede">
        {formatPercent(topic.total_volume_percent)} of the kept conversation. Scale in the sky
        is {topicScale(topic.total_volume_percent, volumeMax).toFixed(2)}× — volume, not virtue.
      </p>
      <MiniCube
        topic={topic}
        selectedPerspectiveId={selectedPerspectiveId}
        onSelectPerspective={onSelectPerspective}
      />
      <div className="perspective-list">
        <h2>Perspectives</h2>
        <p className="topic-row-meta">
          Gold is the loudest view, then ember, sky, violet, jade, rose.
        </p>
        {ranked.map((perspective, index) => (
          <button
            key={perspective.id}
            type="button"
            className={`perspective-card ${selectedPerspectiveId === perspective.id ? 'is-active' : ''}`}
            onClick={() => onSelectPerspective(perspective.id)}
          >
            <div className="perspective-card-head">
              <span className="swatch" style={{ background: spikeColor(index) }} />
              <div>
                <h3>{perspective.title}</h3>
                <p>{perspective.summary}</p>
              </div>
            </div>
            <VolumeBar
              value={perspective.volume_percent}
              color={spikeColor(index)}
              active={selectedPerspectiveId === perspective.id}
            />
            <span className="card-chevron" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
      <EngagementPanel
        topics={topics}
        topic={topic}
        query={engagementQuery}
        onQueryChange={onEngagementQuery}
        onSelectTopic={onSelectTopic}
        onSelectPerspective={onSelectPerspective}
      />
    </div>
  )
}

function PerspectivePanel({
  topic,
  topics,
  perspective,
  isMobile,
  onBack,
  engagementQuery,
  onEngagementQuery,
  onSelectTopic,
  onSelectPerspective,
}) {
  const color = spikeColor(rankPerspectives(topic.perspectives).findIndex((item) => item.id === perspective.id))
  const posts = sortPosts(perspective.representative_posts)

  return (
    <div className="panel is-face">
      {!isMobile && (
        <button type="button" className="back-link" onClick={onBack}>
          ← Back to {topic.name}
        </button>
      )}
      <p className="eyebrow" style={{ color }}>
        {topic.body?.name} · {topic.name}
      </p>
      <h1>{perspective.title}</h1>
      <p className="lede">{perspective.summary}</p>
      <MiniCube topic={topic} selectedPerspectiveId={perspective.id} />
      <p className="caveat">This sentence flattens disagreement inside the cluster.</p>
      <div
        className="perspective-stat"
        style={{ borderColor: hexToRgba(color, 0.4), background: hexToRgba(color, 0.08) }}
      >
        <strong>{formatPercent(perspective.volume_percent)}</strong>
        <span>of this planet&apos;s conversation</span>
      </div>
      <div className="post-feed">
        <h2>Representative posts</h2>
        {posts.map((post) => (
          <article key={`${post.author}-${post.likes}-${post.text.slice(0, 24)}`} className="post-card">
            <header>
              <span>@{post.author}</span>
              <span>{formatNumber(post.likes)} likes</span>
            </header>
            <p>{post.text}</p>
          </article>
        ))}
      </div>
      <EngagementPanel
        topics={topics}
        topic={topic}
        perspective={perspective}
        query={engagementQuery}
        onQueryChange={onEngagementQuery}
        onSelectTopic={onSelectTopic}
        onSelectPerspective={onSelectPerspective}
      />
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
  onSelectLocation,
  onClearSelection,
  onCategory,
  engagementQuery,
  onEngagementQuery,
  volumeMax = 100,
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
          onSelectLocation={onSelectLocation}
          engagementQuery={engagementQuery}
          onEngagementQuery={onEngagementQuery}
          categories={categories}
          category={category}
          counts={counts}
          onCategory={onCategory}
        />
      )}
      {!empty && selectedTopic && !selectedPerspective && (
        <TopicPanel
          topic={selectedTopic}
          topics={topics}
          selectedPerspectiveId={null}
          isMobile={isMobile}
          onSelectPerspective={onSelectPerspective}
          onSelectTopic={onSelectTopic}
          onBack={onClearSelection}
          engagementQuery={engagementQuery}
          onEngagementQuery={onEngagementQuery}
          volumeMax={volumeMax}
        />
      )}
      {!empty && selectedTopic && selectedPerspective && (
        <PerspectivePanel
          topic={selectedTopic}
          topics={topics}
          perspective={selectedPerspective}
          isMobile={isMobile}
          onBack={() => onSelectPerspective(null)}
          engagementQuery={engagementQuery}
          onEngagementQuery={onEngagementQuery}
          onSelectTopic={onSelectTopic}
          onSelectPerspective={onSelectPerspective}
        />
      )}
    </aside>
  )
}
