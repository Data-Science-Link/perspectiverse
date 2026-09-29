import { withSharePercents } from './layout.js'
import { decorateTopics, SOLAR_BODIES } from './planets.js'

export const SYSTEM_SIZE = SOLAR_BODIES.length

export const CATEGORIES = [
  'Sports',
  'Geopolitics',
  'AI',
]

export function filterTopics(topics, category) {
  if (!category || category === 'all') return topics
  return topics.filter((topic) => topic.category === category)
}

export function categoryCounts(topics) {
  const counts = Object.fromEntries(CATEGORIES.map((category) => [category, 0]))
  for (const topic of topics) {
    if (topic.category in counts) counts[topic.category] += 1
  }
  return counts
}

export function solarTopics(topics = [], category = 'all') {
  const filtered = filterTopics(topics, category)
  const ranked = [...filtered].sort((a, b) => {
    const delta = (b.total_volume_percent ?? 0) - (a.total_volume_percent ?? 0)
    if (delta !== 0) return delta
    return String(a.name ?? '').localeCompare(String(b.name ?? ''))
  })
  return decorateTopics(withSharePercents(ranked.slice(0, SYSTEM_SIZE)))
}

export function solarMaxVolume(topics = []) {
  return Math.max(0, ...topics.map((topic) => Number(topic.total_volume_percent) || 0))
}
