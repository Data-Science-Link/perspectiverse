export const CATEGORIES = [
  'Politics',
  'Sports',
  'Technology',
  'Economy',
  'Environment',
  'Health',
  'Education',
  'Media',
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
