import assert from 'node:assert/strict'
import {
  AUTHOR_NAME,
  AUTHOR_LOCATION,
  LINKEDIN_URL,
  SITE_PAGES,
  isSitePage,
  neighborPages,
  normalizePageId,
  pageById,
} from '../src/lib/pages.js'
import { selectionURL, readSelectionFromURL } from '../src/lib/navigation.js'

assert.equal(AUTHOR_NAME, 'Michael Link')
assert.equal(AUTHOR_LOCATION, 'Austin, Texas')
assert.equal(LINKEDIN_URL, 'https://www.linkedin.com/in/data-science-link')
assert.deepEqual(
  SITE_PAGES.map((page) => page.id),
  ['about', 'methodology', 'faq', 'connect', 'donate'],
)

for (const page of SITE_PAGES) {
  assert.equal(isSitePage(page.id), true)
  assert.equal(pageById(page.id).title, page.title)
  assert.ok(page.menuLabel)
  assert.ok(page.heading)
}

assert.equal(normalizePageId('vision'), 'about')
assert.equal(normalizePageId('author'), 'connect')
assert.equal(isSitePage('vision'), true)
assert.equal(isSitePage('nope'), false)
assert.equal(isSitePage(''), false)
assert.equal(pageById('nope'), null)

assert.deepEqual(neighborPages('about').prev, null)
assert.equal(neighborPages('about').next.id, 'methodology')
assert.equal(neighborPages('methodology').prev.id, 'about')
assert.equal(neighborPages('methodology').next.id, 'faq')
assert.equal(neighborPages('connect').prev.id, 'faq')
assert.equal(neighborPages('connect').next.id, 'donate')
assert.equal(neighborPages('donate').prev.id, 'connect')
assert.equal(neighborPages('donate').next, null)

globalThis.window = {
  location: { pathname: '/perspectiverse/', search: '?page=methodology' },
}
assert.equal(
  selectionURL({ category: 'all', topicId: null, perspectiveId: null, page: 'methodology' }),
  '/perspectiverse/?page=methodology',
)
assert.equal(
  selectionURL({ category: 'Geopolitics', topicId: 3, perspectiveId: '3A', page: 'faq' }),
  '/perspectiverse/?category=Geopolitics&page=faq',
)
assert.equal(
  selectionURL({ category: 'all', topicId: 3, perspectiveId: '3A', page: null }),
  '/perspectiverse/?topic=3&face=3A',
)

const snap = readSelectionFromURL()
assert.equal(snap.page, 'methodology')
assert.equal(snap.topicId, null)
assert.equal(snap.perspectiveId, null)

globalThis.window.location.search = '?page=vision'
assert.equal(readSelectionFromURL().page, 'about')

globalThis.window.location.search = '?page=not-a-page&topic=4'
assert.equal(readSelectionFromURL().page, null)
assert.equal(readSelectionFromURL().topicId, 4)

console.log('site pages and page urls ok')
