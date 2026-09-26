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

function WelcomePanel({ data, onSelectTopic }) {
  return (
    <div className="panel">
      <p className="eyebrow">Discourse Universe</p>
      <h1>Perspectiverse</h1>
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
          <strong>{data.topics.length}</strong>
          <span>planets</span>
        </div>
        <div>
          <strong>{data.last_updated}</strong>
          <span>snapshot</span>
        </div>
      </div>
      <div className="how-to">
        <h2>How to read the sky</h2>
        <ul>
          <li>Drag to orbit. Scroll to zoom. Click empty space to pull back.</li>
          <li>Click a planet — or a row below — to lock the camera and open its six faces.</li>
          <li>A long spike is not louder because it is truer. It is louder because more posts clustered there.</li>
        </ul>
      </div>
      <div className="topic-list">
        <h2>Today&apos;s planets</h2>
        {data.topics.map((topic, index) => (
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
              <span className="topic-row-meta">{topic.perspectives.length} perspectives</span>
            </span>
            <VolumeBar value={topic.total_volume_percent} color={topicColor(topic.id)} />
          </button>
        ))}
      </div>
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
        {topic.id === 1 ? 'Central sun' : 'Orbiting planet'}
      </p>
      <h1>{topic.name}</h1>
      <p className="lede">
        {formatPercent(topic.total_volume_percent)} of the week&apos;s conversation. Scale in the
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
          <article key={`${post.author}-${post.likes}`} className="post-card">
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
  selectedTopic,
  selectedPerspective,
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
}) {
  return (
    <aside className="sidebar">
      {!selectedTopic && (
        <WelcomePanel data={data} onSelectTopic={onSelectTopic} />
      )}
      {selectedTopic && !selectedPerspective && (
        <TopicPanel
          topic={selectedTopic}
          selectedPerspectiveId={null}
          onSelectPerspective={onSelectPerspective}
          onBack={onClearSelection}
        />
      )}
      {selectedTopic && selectedPerspective && (
        <PerspectivePanel
          topic={selectedTopic}
          perspective={selectedPerspective}
          onBack={() => onSelectPerspective(null)}
        />
      )}
    </aside>
  )
}
