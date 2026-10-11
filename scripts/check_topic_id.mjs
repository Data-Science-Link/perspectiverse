import assert from 'node:assert/strict'
import {
  parseTopicId,
  migratePerspectiveId,
  resolveTopicId,
  resolveSelection,
  findVisibleTopic,
  reconcileSelectionAfterLoad,
} from '../src/lib/topicId.js'
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

const legacyUrl = { category: 'Technology', topicId: 5, perspectiveId: '5A' }
const legacyResolved = resolveSelection(legacyUrl, data)
assert.equal(legacyResolved.topicId, 'Technology-5')
assert.equal(legacyResolved.category, 'Technology')
assert.equal(legacyResolved.perspectiveId, 'Technology-5A')
assert.equal(findVisibleTopic(data, legacyUrl)?.name, 'App Store')

const legacyReconcile = reconcileSelectionAfterLoad(legacyUrl, data)
assert.equal(legacyReconcile.action, 'sync')
assert.equal(legacyReconcile.selection.topicId, 'Technology-5')
assert.notEqual(legacyReconcile.action, 'clear')

const barePrefixed = { category: 'all', topicId: 'Technology-5', perspectiveId: null }
const bareResolved = resolveSelection(barePrefixed, data)
assert.equal(bareResolved.category, 'Technology')
assert.equal(bareResolved.topicId, 'Technology-5')
assert.equal(findVisibleTopic(data, barePrefixed)?.name, 'App Store')

const bareReconcile = reconcileSelectionAfterLoad(barePrefixed, data)
assert.equal(bareReconcile.action, 'sync')
assert.equal(bareReconcile.selection.category, 'Technology')

assert.equal(
  reconcileSelectionAfterLoad(
    { category: 'Technology', topicId: 'Technology-5', perspectiveId: 'Technology-5A' },
    data,
  ).action,
  'keep',
)

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

globalThis.window.location.search = '?category=Technology&topic=5&face=5A'
const legacyFromUrl = readSelectionFromURL()
const legacyFromUrlPlan = reconcileSelectionAfterLoad(
  {
    category: legacyFromUrl.category,
    topicId: legacyFromUrl.topicId,
    perspectiveId: legacyFromUrl.perspectiveId,
  },
  data,
)
assert.equal(legacyFromUrlPlan.action, 'sync')
assert.equal(legacyFromUrlPlan.selection.topicId, 'Technology-5')

globalThis.window.location.search = '?topic=Technology-5'
const bareFromUrl = readSelectionFromURL()
const barePlan = reconcileSelectionAfterLoad(
  { category: bareFromUrl.category, topicId: bareFromUrl.topicId, perspectiveId: null },
  data,
)
assert.equal(barePlan.action, 'sync')
assert.equal(barePlan.selection.category, 'Technology')

console.log('topic id parsing, legacy section links, and post-load reconcile ok')
