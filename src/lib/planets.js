export const SOLAR_BODIES = [
  { key: 'sun', name: 'Sun', color: '#f4c14e', emissive: 1.35, glow: true },
  { key: 'mercury', name: 'Mercury', color: '#c5c8ce', emissive: 0.08 },
  { key: 'venus', name: 'Venus', color: '#f3d392', emissive: 0.14 },
  { key: 'earth', name: 'Earth', color: '#4aa3e6', emissive: 0.12 },
  { key: 'mars', name: 'Mars', color: '#e25a2b', emissive: 0.1 },
  { key: 'jupiter', name: 'Jupiter', color: '#e8be7a', emissive: 0.08 },
  { key: 'saturn', name: 'Saturn', color: '#f0ddb0', emissive: 0.1, rings: true },
  { key: 'uranus', name: 'Uranus', color: '#7ee0d8', emissive: 0.14 },
  { key: 'neptune', name: 'Neptune', color: '#4b86f0', emissive: 0.14 },
  { key: 'pluto', name: 'Pluto', color: '#e0b48c', emissive: 0.08 },
]

export function bodyForRank(rank) {
  const index = Number(rank)
  if (!Number.isFinite(index) || index < 0) return SOLAR_BODIES[0]
  return SOLAR_BODIES[Math.min(index, SOLAR_BODIES.length - 1)]
}

export function decorateTopics(topics = []) {
  return topics.map((topic, index) => ({
    ...topic,
    body: bodyForRank(index),
  }))
}

export function decorateVisibleTopics(allTopics = [], visibleTopics = []) {
  const ranks = new Map(allTopics.map((topic, index) => [topic.id, index]))
  return visibleTopics.map((topic) => ({
    ...topic,
    body: bodyForRank(ranks.get(topic.id) ?? 0),
  }))
}
