import { categoryCounts } from '../lib/categories'
import { hexToRgba, spikeColor, topicColor } from '../lib/colors'
import { formatNumber, formatPercent, sortPosts, topicScale } from '../lib/layout'
import MiniCube from './MiniCube'

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

function sourceLine(data) {
  if (data.mode === 'demo' || data.source === 'synthetic') {
    return 'a synthetic sample written for this demo'
  }
  if (data.source === 'bluesky') {
    return 'public English posts on Bluesky'
  }
  if (data.source === 'fixture') {
    return 'a local fixture, not a live feed'
  }
  return 'the snapshot bundled with this page'
}

function FilterStrip({ categories, category, counts, onCategory }) {
  return (
    <div className="filter-strip" role="tablist" aria-label="Category">
      <button
        type="button"
        className={`filter-chip ${category === 'all' ? 'is-active' : ''}`}
        onClick={() => onCategory('all')}
      >
        All
      </button>
      {categories.map((name) => (
        <button
          key={name}
          type="button"
          className={`filter-chip ${category === name ? 'is-active' : ''}`}
          onClick={() => onCategory(name)}
        >
          {name}
          <span className="filter-count">{counts[name] ?? 0}</span>
        </button>
      ))}
    </div>
  )
}

function WelcomePanel({ data, topics, onSelectTopic }) {
  const windowHours = data.window_hours ?? 168
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
        A gravitational map of a week of public conversation. The largest topic sits at the
        center. The rest orbit by volume. Each planet is a cube whose six spikes are the
        dominant perspectives inside that topic.
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
      <div className="how-to">
        <h2>How to read this</h2>
        <ul>
          <li>
            Source: {sourceLine(data)}. Window: the last {windowHours} hours.
          </li>
          <li>Drag to orbit. Scroll to zoom. Click empty space to pull back.</li>
          <li>Click a planet — or a row below — to lock the camera and turn that cube.</li>
          <li>A long spike is not louder because it is truer. It is louder because more posts clustered there.</li>
        </ul>
      </div>
      <div className="how-to">
        <h2>What this is not</h2>
        <ul>
          <li>This is internet discourse, not a poll of humanity. Bluesky is not everyone.</li>
          <li>A face summary collapses dissent inside that cluster. Minority views can disappear into one sentence.</li>
          <li>Posts that fit no planet are left out of the percentages.</li>
        </ul>
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
            <span className="swatch" style={{ background: topicColor(topic.id) }} />
            <span className="topic-row-copy">
              <span className="topic-row-name">
                {index === 0 ? 'Sun' : `Orbit ${index}`} · {topic.name}
              </span>
              <span className="topic-row-meta">
                {topic.category} · {topic.perspectives.length} perspectives
              </span>
            </span>
            <VolumeBar value={topic.total_volume_percent} color={topicColor(topic.id)} />
          </button>
        ))}
      </div>
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

function TopicPanel({ topic, selectedPerspectiveId, onSelectPerspective, onBack }) {
  return (
    <div className="panel">
      <button type="button" className="back-link" onClick={onBack}>
        All topics
      </button>
      <p className="eyebrow" style={{ color: topicColor(topic.id) }}>
        {topic.category} · {topic.id === 1 ? 'Central sun' : 'Orbiting planet'}
      </p>
      <h1>{topic.name}</h1>
      <p className="lede">
        {formatPercent(topic.total_volume_percent)} of the kept conversation. Scale in the
        sky is {topicScale(topic.total_volume_percent).toFixed(2)}× the baseline cube — volume,
        not virtue.
      </p>
      <MiniCube
        topic={topic}
        selectedPerspectiveId={selectedPerspectiveId}
        onSelectPerspective={onSelectPerspective}
      />
      <div className="perspective-list">
        {topic.perspectives.map((perspective, index) => (
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
          </button>
        ))}
      </div>
    </div>
  )
}

function PerspectivePanel({ topic, perspective, onBack }) {
  const index = topic.perspectives.findIndex((item) => item.id === perspective.id)
  const color = spikeColor(index)
  const posts = sortPosts(perspective.representative_posts)

  return (
    <div className="panel">
      <button type="button" className="back-link" onClick={onBack}>
        Back to {topic.name}
      </button>
      <p className="eyebrow" style={{ color }}>
        {topic.name} · Face {perspective.id}
      </p>
      <h1>{perspective.title}</h1>
      <p className="lede">{perspective.summary}</p>
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
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
  onCategory,
}) {
  const counts = categoryCounts(data.topics)
  const empty = topics.length === 0

  return (
    <aside className="sidebar">
      <FilterStrip
        categories={categories}
        category={category}
        counts={counts}
        onCategory={onCategory}
      />
      {empty && <EmptyCategory category={category} onShowAll={() => onCategory('all')} />}
      {!empty && !selectedTopic && (
        <WelcomePanel data={data} topics={topics} onSelectTopic={onSelectTopic} />
      )}
      {!empty && selectedTopic && !selectedPerspective && (
        <TopicPanel
          topic={selectedTopic}
          selectedPerspectiveId={null}
          onSelectPerspective={onSelectPerspective}
          onBack={onClearSelection}
        />
      )}
      {!empty && selectedTopic && selectedPerspective && (
        <PerspectivePanel
          topic={selectedTopic}
          perspective={selectedPerspective}
          onBack={() => onSelectPerspective(null)}
        />
      )}
    </aside>
  )
}
