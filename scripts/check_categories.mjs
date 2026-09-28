import assert from 'node:assert/strict'
import { CATEGORIES, categoryCounts, filterTopics, skyTopics } from '../src/lib/categories.js'

const topics = [
  { id: 1, category: 'Sports', name: 'A', total_volume_percent: 12 },
  { id: 2, category: 'Health', name: 'B', total_volume_percent: 8 },
  { id: 3, category: 'Sports', name: 'C', total_volume_percent: 20 },
]

assert.equal(filterTopics(topics, 'all').length, 3)
assert.equal(filterTopics(topics, 'Sports').length, 2)
assert.equal(filterTopics(topics, 'Politics').length, 0)
assert.equal(categoryCounts(topics).Sports, 2)
assert.equal(categoryCounts(topics).Politics, 0)
assert.ok(CATEGORIES.includes('Entertainment'))
assert.ok(CATEGORIES.includes('Religion'))

const sportsSky = skyTopics(topics, 'Sports')
assert.equal(sportsSky.length, 2)
assert.equal(sportsSky[0].name, 'C')
assert.equal(sportsSky[0].body.key, 'sun')
assert.equal(sportsSky[1].body.key, 'mercury')

console.log('category filter helper ok')
