export const FEEDBACK_URL =
  'https://github.com/Data-Science-Link/perspectiverse/issues/new?title=Feedback'
export const REPO_URL = 'https://github.com/Data-Science-Link/perspectiverse'
export const AUTHOR_GITHUB_URL = 'https://github.com/Data-Science-Link'
export const SPONSORS_URL = 'https://github.com/sponsors/Data-Science-Link'
export const LINKEDIN_URL = 'https://www.linkedin.com/in/data-science-link'
export const AUTHOR_NAME = 'Michael Link'
export const AUTHOR_HANDLE = 'Data-Science-Link'
export const AUTHOR_LOCATION = 'Austin, Texas'

/** Canonical site pages (hamburger + URL `?page=`). */
export const SITE_PAGES = [
  {
    id: 'about',
    title: 'About',
    menuLabel: 'About',
    subtitle: 'What this is and why it exists',
    eyebrow: 'About',
    heading: 'A week of public talk, mapped without taking sides',
  },
  {
    id: 'methodology',
    title: 'Methodology',
    menuLabel: 'Methodology',
    subtitle: 'Source → filters → planets → perspectives',
    eyebrow: 'Methodology',
    heading: 'How the map is built',
  },
  {
    id: 'faq',
    title: 'FAQ',
    menuLabel: 'FAQ',
    subtitle: 'Short answers',
    eyebrow: 'FAQ',
    heading: 'Common questions',
  },
  {
    id: 'connect',
    title: 'Connect',
    menuLabel: 'Connect',
    subtitle: 'Author, GitHub, feedback',
    eyebrow: 'Connect',
    heading: 'People and links',
  },
  {
    id: 'donate',
    title: 'Donate',
    menuLabel: 'Donate',
    subtitle: 'Keep Perspectiverse public',
    eyebrow: 'Donate',
    heading: 'Support the observatory',
  },
]

/** Legacy `?page=` ids still open the merged destination. */
export const PAGE_ALIASES = {
  vision: 'about',
  author: 'connect',
}

const PAGE_IDS = new Set(SITE_PAGES.map((page) => page.id))

export function normalizePageId(id) {
  if (typeof id !== 'string' || id === '') return null
  if (PAGE_IDS.has(id)) return id
  const alias = PAGE_ALIASES[id]
  return alias && PAGE_IDS.has(alias) ? alias : null
}

export function isSitePage(id) {
  return normalizePageId(id) != null
}

export function pageById(id) {
  const canonical = normalizePageId(id)
  return canonical ? SITE_PAGES.find((page) => page.id === canonical) ?? null : null
}

export function neighborPages(id) {
  const canonical = normalizePageId(id)
  const index = SITE_PAGES.findIndex((page) => page.id === canonical)
  if (index < 0) return { prev: null, next: null }
  return {
    prev: SITE_PAGES[index - 1] ?? null,
    next: SITE_PAGES[index + 1] ?? null,
  }
}
