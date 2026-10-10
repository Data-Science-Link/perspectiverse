import { solarTopics } from './categories.js'

const SECTION_TOPIC_ID = /^(World|Politics|Business|Technology|Sports|Culture|Health|Environment|Education|Other)-(\d+)$/

export function parseTopicId(raw) {
  if (raw == null || raw === '') return null
  const text = String(raw).trim()
  if (/^\d+$/.test(text)) return Number(text)
  if (SECTION_TOPIC_ID.test(text)) return text
  return null
}

export function sectionForPrefixedTopicId(topicId) {
  if (typeof topicId !== 'string') return null
  const match = topicId.match(SECTION_TOPIC_ID)
  return match ? match[1] : null
}

export function resolveTopicId(category, topicId, data) {
  if (topicId == null) return null
  if (typeof topicId === 'string' && topicId.includes('-')) return topicId
  if (category && category !== 'all' && data?.sections?.[category]) {
    const prefixed = `${category}-${topicId}`
    if (data.sections[category].some((topic) => topic.id === prefixed)) return prefixed
    if (data.sections[category].some((topic) => topic.id === topicId)) return topicId
  }
  return topicId
}

export function migratePerspectiveId(topicId, perspectiveId) {
  if (!perspectiveId || topicId == null) return perspectiveId
  const topicKey = String(topicId)
  if (String(perspectiveId).startsWith(topicKey)) return perspectiveId
  const legacy = /^(\d+)([A-F])$/.exec(String(perspectiveId))
  if (!legacy) return perspectiveId
  if (`${legacy[1]}` === topicKey) return `${topicId}${legacy[2]}`
  if (topicKey.includes('-')) {
    const rank = topicKey.split('-').pop()
    if (legacy[1] === rank) return `${topicId}${legacy[2]}`
  }
  return perspectiveId
}

/** Normalize category, topic, and face after data is available (legacy + bare prefixed links). */
export function resolveSelection({ category, topicId, perspectiveId }, data) {
  const initialCategory = category || 'all'
  if (topicId != null && sectionForPrefixedTopicId(topicId) && data?.sections) {
    const section = sectionForPrefixedTopicId(topicId)
    if (data.sections[section]?.some((topic) => topic.id === topicId)) {
      return {
        category: section,
        topicId,
        perspectiveId: migratePerspectiveId(topicId, perspectiveId),
      }
    }
  }
  const resolvedTopic = resolveTopicId(initialCategory, topicId, data)
  let resolvedCategory = initialCategory
  const section = sectionForPrefixedTopicId(resolvedTopic)
  if (section && data?.sections?.[section]?.some((topic) => topic.id === resolvedTopic)) {
    resolvedCategory = section
  }
  return {
    category: resolvedCategory,
    topicId: resolvedTopic,
    perspectiveId: migratePerspectiveId(resolvedTopic, perspectiveId),
  }
}

export function findVisibleTopic(data, selection) {
  if (!data) return null
  const resolved = resolveSelection(selection, data)
  if (resolved.topicId == null) return null
  const pool = solarTopics(data, resolved.category)
  return pool.find((topic) => topic.id === resolved.topicId) ?? null
}

/** Mirrors App post-load logic: resolve first, only clear when still missing after resolve. */
export function reconcileSelectionAfterLoad(selection, data) {
  const resolved = resolveSelection(selection, data)
  const needsSync =
    resolved.category !== selection.category ||
    resolved.topicId !== selection.topicId ||
    resolved.perspectiveId !== selection.perspectiveId
  if (needsSync) {
    return { action: 'sync', selection: resolved }
  }
  if (resolved.topicId != null && !findVisibleTopic(data, resolved)) {
    return {
      action: 'clear',
      selection: { category: resolved.category, topicId: null, perspectiveId: null },
    }
  }
  return { action: 'keep', selection: resolved }
}
