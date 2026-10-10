import assert from 'node:assert/strict'
import { parseTopicId, migratePerspectiveId, resolveTopicId } from '../src/lib/topicId.js'
import { readSelectionFromURL, selectionURL } from '../src/lib/navigation.js'

assert.equal(parseTopicId('5'), 5)
assert.equal(parseTopicId('Technology-5'), 'Technology-5')
assert.equal(parseTopicId('nope'), null)

const data = {
  topics: [{ id: 5, name: 'Angie Nixon' }],
  sections: {
    Technology: [{ id: 'Technology-5', name: 'App Store' }],
  },
}
assert.equal(resolveTopicId('Technology', 5, data), 'Technology-5')
assert.equal(resolveTopicId('all', 5, data), 5)
assert.equal(migratePerspectiveId('Technology-5', '5A'), 'Technology-5A')

globalThis.window = {
  location: {
    pathname: '/perspectiverse/',
    search: '?category=Technology&topic=Technology-5&face=Technology-5A',
  },
}
const fromUrl = readSelectionFromURL()
assert.equal(fromUrl.topicId, 'Technology-5')
assert.equal(fromUrl.perspectiveId, 'Technology-5A')
assert.equal(
  selectionURL({ category: 'Technology', topicId: 'Technology-5', perspectiveId: 'Technology-5A' }),
  '/perspectiverse/?category=Technology&topic=Technology-5&face=Technology-5A',
)

console.log('topic id parsing and legacy section links ok')
