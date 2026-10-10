const SECTION_TOPIC_ID = /^(World|Politics|Business|Technology|Sports|Culture|Health|Environment|Education|Other)-\d+$/

export function parseTopicId(raw) {
  if (raw == null || raw === '') return null
  const text = String(raw).trim()
  if (/^\d+$/.test(text)) return Number(text)
  if (SECTION_TOPIC_ID.test(text)) return text
  return null
}

export function resolveTopicId(category, topicId, data) {
  if (topicId == null) return null
  if (typeof topicId === 'string' && topicId.includes('-')) return topicId
  if (category && category !== 'all' && data?.sections?.[category]) {
    const prefixed = `${category}-${topicId}`
    if (data.sections[category].some((topic) => topic.id === prefixed)) return prefixed
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
