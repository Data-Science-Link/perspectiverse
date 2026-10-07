import { withSharePercents } from './layout.js'
import { decorateTopics, SOLAR_BODIES } from './planets.js'

export const SYSTEM_SIZE = SOLAR_BODIES.length

export const CATEGORIES = [
  'World',
  'Politics',
  'Business',
  'Technology',
  'Sports',
  'Culture',
  'Health',
  'Environment',
  'Education',
  'Other',
]

export function filterTopics(topics, category) {
  if (!category || category === 'all') return topics
  return topics.filter((topic) => topic.category === category)
}

/**
 * Count planets per category. When per-section topics are available in
 * `data.sections`, use those counts so the dropdown shows how many section
 * planets exist rather than how many global planets happen to be tagged with
 * that category.
 */
export function categoryCounts(data) {
  const topics = Array.isArray(data) ? data : (data?.topics ?? [])
  const sections = Array.isArray(data) ? null : (data?.sections ?? null)
  const counts = Object.fromEntries(CATEGORIES.map((category) => [category, 0]))
  if (sections) {
    for (const [category, sectionTopics] of Object.entries(sections)) {
      if (category in counts) counts[category] = sectionTopics.length
    }
  } else {
    for (const topic of topics) {
      if (topic.category in counts) counts[topic.category] += 1
    }
  }
  return counts
}

/**
 * Return the decorated topic list for the solar system view.
 *
 * When `data.sections[category]` exists the section has its own clustering
 * pass, so use those planets directly instead of filtering the global top 10.
 * "All topics" always uses the global list.
 */
export function solarTopics(data = [], category = 'all') {
  const topics = Array.isArray(data) ? data : (data?.topics ?? [])
  const sections = Array.isArray(data) ? null : (data?.sections ?? null)

  let pool
  if (category && category !== 'all' && sections?.[category]) {
    pool = sections[category]
  } else {
    pool = filterTopics(topics, category)
  }

  const ranked = [...pool].sort((a, b) => {
    const delta = (b.total_volume_percent ?? 0) - (a.total_volume_percent ?? 0)
    if (delta !== 0) return delta
    return String(a.name ?? '').localeCompare(String(b.name ?? ''))
  })
  return decorateTopics(withSharePercents(ranked.slice(0, SYSTEM_SIZE)))
}

export function solarMaxVolume(topics = []) {
  return Math.max(0, ...topics.map((topic) => Number(topic.total_volume_percent) || 0))
}
