export const SOLAR_BODIES = [
  { key: 'sun', name: 'Sun', color: '#f4c14e', emissive: 1.35, glow: true },
  { key: 'mercury', name: 'Mercury', color: '#b5a394', emissive: 0.08 },
  { key: 'venus', name: 'Venus', color: '#e6c27a', emissive: 0.12 },
  { key: 'earth', name: 'Earth', color: '#3d8fd1', emissive: 0.1 },
  { key: 'mars', name: 'Mars', color: '#c1440e', emissive: 0.1 },
  { key: 'jupiter', name: 'Jupiter', color: '#d4a056', emissive: 0.08 },
  { key: 'saturn', name: 'Saturn', color: '#e6d3a3', emissive: 0.1, rings: true },
  { key: 'uranus', name: 'Uranus', color: '#7ec8c8', emissive: 0.12 },
  { key: 'neptune', name: 'Neptune', color: '#3b6fd4', emissive: 0.12 },
  { key: 'pluto', name: 'Pluto', color: '#c4a574', emissive: 0.06 },
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
