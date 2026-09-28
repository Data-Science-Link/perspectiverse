import { engage, verdictCopy } from '../lib/engagement'
import { hexToRgba, spikeColor, topicColor } from '../lib/colors'
import { formatNumber, formatPercent } from '../lib/layout'

const STARTERS = {
  sky: [
    'AI is going to create more jobs, not fewer',
    'Housing costs matter more than culture war',
    'Nike',
  ],
  planet: [
    'This is overblown',
    'Why are people thinking that?',
    'What am I missing?',
  ],
  face: [
    'Why do you think that?',
    'I disagree',
    'What would the other faces say?',
  ],
}

function QuoteList({ title, rows, empty }) {
  if (!rows.length) {
    return empty ? <p className="engage-empty">{empty}</p> : null
  }
  return (
    <div className="engage-quotes">
      <h3>{title}</h3>
      {rows.map((row) => (
        <article key={`${row.author}-${row.text.slice(0, 32)}`} className="post-card">
          <header>
            <span>@{row.author}</span>
            <span>{formatNumber(row.likes)} likes</span>
          </header>
          <p>{row.text}</p>
          {row.faceTitle && (
            <p className="engage-quote-meta">
              {row.topicName} · {row.faceTitle}
            </p>
          )}
        </article>
      ))}
    </div>
  )
}

export default function EngagementPanel({
  topics,
  topic = null,
  perspective = null,
  query,
  onQueryChange,
  onSelectTopic,
  onSelectPerspective,
  onSelectLocation,
  compact = false,
}) {
  const scope = perspective ? 'face' : topic ? 'planet' : 'sky'
  const result = query.trim()
    ? engage(query, topics, {
        topicId: topic?.id ?? null,
        perspectiveId: perspective?.id ?? null,
      })
    : null
  const verdict = result ? verdictCopy(result) : null
  const eyebrow = scope === 'face'
    ? 'This face'
    : scope === 'planet'
      ? 'This planet'
      : 'This week’s sky'

  const submitFollowup = (item) => {
    if (item.action === 'open-topic' && item.topicId != null) {
      onQueryChange(item.query ?? query)
      if (onSelectLocation) {
        onSelectLocation({ topicId: item.topicId, perspectiveId: null })
      } else {
        onSelectTopic(item.topicId)
      }
      return
    }
    if (item.action === 'open-face' && item.faceId) {
      onQueryChange(item.query ?? query)
      if (onSelectLocation && item.topicId != null) {
        onSelectLocation({ topicId: item.topicId, perspectiveId: item.faceId })
      } else {
        onSelectPerspective(item.faceId)
      }
      return
    }
    onQueryChange(item.query)
  }

  return (
    <section className={`engage ${compact ? 'is-compact' : ''}`} aria-label="Test your take">
      <p className="eyebrow">Anti-echo · {eyebrow}</p>
      <h2>Test your take</h2>
      {!compact && (
        <p className="lede">
          Type the argument you think is the story — or a brand. The snapshot answers
          with other people’s words, and whether you are the loud face, a minority
          spike, or not on this sky at all.
        </p>
      )}
      <form
        className="engage-form"
        onSubmit={(event) => {
          event.preventDefault()
        }}
      >
        <label className="sr-only" htmlFor={`engage-${scope}`}>
          Your take
        </label>
        <textarea
          id={`engage-${scope}`}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={compact ? 2 : 3}
          placeholder={scope === 'sky' ? 'A claim, a brand, a question…' : 'Ask why, push back, or name the thing you think they mean…'}
        />
      </form>
      <div className="engage-starters">
        {STARTERS[scope].map((starter) => (
          <button
            key={starter}
            type="button"
            className="filter-chip"
            onClick={() => onQueryChange(starter)}
          >
            {starter}
          </button>
        ))}
      </div>
      {verdict && (
        <div
          className={`engage-verdict is-${result.presence}`}
          role="status"
          aria-live="polite"
        >
          <strong>{verdict.title}</strong>
          <p>{verdict.body}</p>
          {result.bestTopic && scope === 'sky' && (
            <p className="engage-verdict-meta">
              Best overlap: {result.bestTopic.bodyName ? `${result.bestTopic.bodyName} · ` : ''}
              {result.bestTopic.name} · {formatPercent(result.bestTopic.volume)} of the sky
            </p>
          )}
          {result.bestFace && scope !== 'sky' && (
            <p className="engage-verdict-meta">
              Best overlap: {result.bestFace.title} · {formatPercent(result.bestFace.volume)} of this planet
            </p>
          )}
        </div>
      )}
      {result?.faces?.length > 0 && scope === 'planet' && (
        <div className="engage-faces">
          {result.faces.map((face) => {
            const color = spikeColor(face.rank)
            return (
              <button
                key={face.id}
                type="button"
                className="engage-face"
                style={{ borderColor: hexToRgba(color, 0.45), background: hexToRgba(color, 0.08) }}
                onClick={() => onSelectPerspective(face.id)}
              >
                <span className="swatch" style={{ background: color }} />
                <span>
                  <strong>{face.title}</strong>
                  <em>{formatPercent(face.volume)} · {face.hits} overlapping posts</em>
                </span>
              </button>
            )
          })}
        </div>
      )}
      {result?.topics?.length > 0 && scope === 'sky' && (
        <div className="engage-faces">
          {result.topics.slice(0, 4).map((hit) => {
            const topicMatch = topics.find((item) => item.id === hit.id)
            const color = topicColor(hit.id, topicMatch?.body)
            return (
              <button
                key={hit.id}
                type="button"
                className="engage-face"
                style={{ borderColor: hexToRgba(color, 0.45), background: hexToRgba(color, 0.08) }}
                onClick={() => onSelectTopic(hit.id)}
              >
                <span className="swatch" style={{ background: color }} />
                <span>
                  <strong>{hit.bodyName ? `${hit.bodyName} · ${hit.name}` : hit.name}</strong>
                  <em>{formatPercent(hit.volume)} · {hit.hits} overlapping posts</em>
                </span>
              </button>
            )
          })}
        </div>
      )}
      {result && (
        <>
          <QuoteList
            title="Their words"
            rows={result.supporting}
            empty={result.presence === 'absent' ? 'No representative post overlapped enough to quote.' : null}
          />
          {result.counter.length > 0 && result.presence !== 'absent' && (
            <QuoteList title="The other spike" rows={result.counter} />
          )}
          {result.followups.length > 0 && (
            <div className="engage-followups">
              <h3>Ask a follow-up</h3>
              {result.followups.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="filter-chip"
                  onClick={() => submitFollowup(item)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
          <p className="caveat">
            Extractive overlap on the representative posts already in this snapshot — not an
            LLM, not the full firehose. A long spike is still not truer.
          </p>
        </>
      )}
    </section>
  )
}
