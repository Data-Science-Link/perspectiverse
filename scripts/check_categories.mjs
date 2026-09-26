import assert from 'node:assert/strict'
import { categoryCounts, filterTopics } from '../src/lib/categories.js'

const topics = [
  { id: 1, category: 'Sports', name: 'A' },
  { id: 2, category: 'Health', name: 'B' },
]

assert.equal(filterTopics(topics, 'all').length, 2)
assert.equal(filterTopics(topics, 'Sports').length, 1)
assert.equal(filterTopics(topics, 'Politics').length, 0)
assert.equal(categoryCounts(topics).Sports, 1)
assert.equal(categoryCounts(topics).Politics, 0)
console.log('category filter helper ok')
