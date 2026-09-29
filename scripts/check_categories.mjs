import assert from 'node:assert/strict'
import { CATEGORIES, categoryCounts, filterTopics, solarTopics } from '../src/lib/categories.js'
import { allocatePercents } from '../src/lib/layout.js'

const topics = [
  { id: 1, category: 'Sports', name: 'A', total_volume_percent: 12 },
  { id: 2, category: 'AI', name: 'B', total_volume_percent: 8 },
  { id: 3, category: 'Sports', name: 'C', total_volume_percent: 20 },
]

assert.equal(filterTopics(topics, 'all').length, 3)
assert.equal(filterTopics(topics, 'Sports').length, 2)
assert.equal(filterTopics(topics, 'Geopolitics').length, 0)
assert.equal(categoryCounts(topics).Sports, 2)
assert.equal(categoryCounts(topics).Geopolitics, 0)
assert.ok(CATEGORIES.includes('Sports'))
assert.ok(CATEGORIES.includes('Geopolitics'))
assert.ok(CATEGORIES.includes('AI'))
assert.equal(CATEGORIES.length, 3)

const sportsSystem = solarTopics(topics, 'Sports')
assert.equal(sportsSystem.length, 2)
assert.equal(sportsSystem[0].name, 'C')
assert.equal(sportsSystem[0].body.key, 'sun')
assert.equal(sportsSystem[1].body.key, 'mercury')
assert.equal(
  Math.round(sportsSystem.reduce((sum, topic) => sum + topic.total_volume_percent, 0) * 10),
  1000,
)
assert.equal(sportsSystem[0].total_volume_percent + sportsSystem[1].total_volume_percent, 100)

const geoLike = solarTopics(
  [
    { id: 1, category: 'Geopolitics', name: 'Ukraine Aid', total_volume_percent: 3.7 },
    { id: 2, category: 'Geopolitics', name: 'Gaza Ceasefire', total_volume_percent: 2.3 },
    { id: 3, category: 'Geopolitics', name: 'China Tariffs', total_volume_percent: 1.7 },
    { id: 4, category: 'Geopolitics', name: 'NATO Spend', total_volume_percent: 1.3 },
    { id: 5, category: 'Geopolitics', name: 'Election Law', total_volume_percent: 1 },
    { id: 6, category: 'Geopolitics', name: 'Iran Sanctions', total_volume_percent: 0.9 },
    { id: 7, category: 'Geopolitics', name: 'Taiwan Strait', total_volume_percent: 0.8 },
    { id: 8, category: 'Geopolitics', name: 'Border Policy', total_volume_percent: 0.5 },
    { id: 9, category: 'Geopolitics', name: 'UN Vote', total_volume_percent: 0.4 },
    { id: 10, category: 'Geopolitics', name: 'Oil Embargo', total_volume_percent: 0.4 },
    { id: 11, category: 'AI', name: 'AI Futures', total_volume_percent: 5.1 },
  ],
  'Geopolitics',
)
assert.equal(geoLike.length, 10)
assert.equal(
  Number(geoLike.reduce((sum, topic) => sum + topic.total_volume_percent, 0).toFixed(1)),
  100,
)

const shares = allocatePercents([5.1, 4.6, 3.7, 3.2, 3.1, 2.9, 2.8, 2.5, 2.3, 2.3])
assert.equal(Number(shares.reduce((sum, value) => sum + value, 0).toFixed(1)), 100)
assert.equal(shares.length, 10)

console.log('category filter helper ok')
