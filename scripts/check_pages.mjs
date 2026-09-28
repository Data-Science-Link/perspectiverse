import assert from 'node:assert/strict'
import {
  AUTHOR_NAME,
  LINKEDIN_URL,
  SITE_PAGES,
  isSitePage,
  neighborPages,
  pageById,
} from '../src/lib/pages.js'
import { selectionURL, readSelectionFromURL } from '../src/lib/navigation.js'

assert.equal(AUTHOR_NAME, 'Michael Link')
assert.equal(LINKEDIN_URL, 'https://www.linkedin.com/in/data-science-link')
assert.deepEqual(
  SITE_PAGES.map((page) => page.id),
  ['vision', 'about', 'author', 'connect', 'methodology', 'faq', 'donate'],
)

for (const page of SITE_PAGES) {
  assert.equal(isSitePage(page.id), true)
  assert.equal(pageById(page.id).title, page.title)
  assert.ok(page.menuLabel)
  assert.ok(page.heading)
}

assert.equal(isSitePage('nope'), false)
assert.equal(isSitePage(''), false)
assert.equal(pageById('nope'), null)

assert.deepEqual(neighborPages('vision').prev, null)
assert.equal(neighborPages('vision').next.id, 'about')
assert.equal(neighborPages('about').prev.id, 'vision')
assert.equal(neighborPages('about').next.id, 'author')
assert.equal(neighborPages('author').next.id, 'connect')
assert.equal(neighborPages('connect').prev.id, 'author')
assert.equal(neighborPages('connect').next.id, 'methodology')
assert.equal(neighborPages('donate').prev.id, 'faq')
assert.equal(neighborPages('donate').next, null)

globalThis.window = {
  location: { pathname: '/perspectiverse/', search: '?page=methodology' },
}
assert.equal(
  selectionURL({ category: 'all', topicId: null, perspectiveId: null, page: 'methodology' }),
  '/perspectiverse/?page=methodology',
)
assert.equal(
  selectionURL({ category: 'Politics', topicId: 3, perspectiveId: '3A', page: 'faq' }),
  '/perspectiverse/?category=Politics&page=faq',
)
assert.equal(
  selectionURL({ category: 'all', topicId: 3, perspectiveId: '3A', page: null }),
  '/perspectiverse/?topic=3&face=3A',
)

const snap = readSelectionFromURL()
assert.equal(snap.page, 'methodology')
assert.equal(snap.topicId, null)
assert.equal(snap.perspectiveId, null)

globalThis.window.location.search = '?page=not-a-page&topic=4'
assert.equal(readSelectionFromURL().page, null)
assert.equal(readSelectionFromURL().topicId, 4)

console.log('site pages and page urls ok')
