import { useEffect, useState } from 'react'
import { formatNumber, sortPosts } from '../lib/layout'

export const POST_PREVIEW_COUNT = 5

export function TopTerms({ terms }) {
  const items = (terms || []).filter((term) => String(term).trim())
  if (!items.length) return null
  return (
    <div className="top-terms" aria-label="Top terms in this view">
      {items.map((term) => (
        <span key={term} className="top-term">{term}</span>
      ))}
    </div>
  )
}

export function LazyPostFeed({ posts, previewCount = POST_PREVIEW_COUNT, faceKey = '' }) {
  const sorted = sortPosts(posts || [])
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setExpanded(false)
  }, [faceKey])

  const hidden = sorted.length > previewCount
  const visible = expanded || !hidden ? sorted : sorted.slice(0, previewCount)

  return (
    <>
      {visible.map((post) => (
        <article key={`${post.author}-${post.likes}-${post.text?.slice(0, 24)}`} className="post-card">
          <header>
            <span>@{post.author}</span>
            <span>{formatNumber(post.likes || 0)} likes</span>
          </header>
          <p>{post.text}</p>
        </article>
      ))}
      {hidden && (
        <button
          type="button"
          className="text-button post-expand"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Show fewer posts' : `Show ${sorted.length - previewCount} more posts`}
        </button>
      )}
      {sorted.length === 0 && <p className="topic-row-meta">No example posts.</p>}
    </>
  )
}
