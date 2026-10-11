import { isSitePage, normalizePageId } from './pages.js'
import { parseTopicId } from './topicId.js'

export function readSelectionFromURL() {
  const params = new URLSearchParams(window.location.search)
  const category = params.get('category') || 'all'
  const topicRaw = params.get('topic')
  const topicId = parseTopicId(topicRaw)
  const face = params.get('face')
  const pageRaw = params.get('page')
  const page = normalizePageId(pageRaw)
  return {
    category,
    topicId: page ? null : topicId,
    perspectiveId: page ? null : face || null,
    page,
  }
}

export function selectionURL({ category, topicId, perspectiveId, page }) {
  const params = new URLSearchParams()
  if (category && category !== 'all') params.set('category', category)
  if (isSitePage(page)) {
    params.set('page', page)
  } else {
    if (topicId != null) params.set('topic', String(topicId))
    if (perspectiveId) params.set('face', perspectiveId)
  }
  const search = params.toString()
  return `${window.location.pathname}${search ? `?${search}` : ''}`
}

export function writeSelectionToURL(selection, mode = 'push') {
  const next = selectionURL(selection)
  const current = `${window.location.pathname}${window.location.search}`
  if (next === current) return
  const state = {
    category: selection.category ?? 'all',
    topicId: selection.topicId ?? null,
    perspectiveId: selection.perspectiveId ?? null,
    page: isSitePage(selection.page) ? selection.page : null,
  }
  if (mode === 'replace') {
    window.history.replaceState(state, '', next)
    return
  }
  window.history.pushState(state, '', next)
}

export function resetScroll(scroller) {
  window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
  if (scroller) scroller.scrollTop = 0
  const pageScroller = scroller?.querySelector?.('.site-page')
  if (pageScroller) pageScroller.scrollTop = 0
}
