export const FEEDBACK_URL =
  'https://github.com/Data-Science-Link/perspectiverse/issues/new?title=Feedback'
export const REPO_URL = 'https://github.com/Data-Science-Link/perspectiverse'
export const AUTHOR_GITHUB_URL = 'https://github.com/Data-Science-Link'
export const SPONSORS_URL = 'https://github.com/sponsors/Data-Science-Link'
export const LINKEDIN_URL = 'https://www.linkedin.com/in/data-science-link'
export const AUTHOR_NAME = 'Michael Link'
export const AUTHOR_HANDLE = 'Data-Science-Link'

export const SITE_PAGES = [
  {
    id: 'vision',
    title: 'Vision',
    menuLabel: 'Vision',
    subtitle: 'Why this observatory exists',
    eyebrow: 'Vision',
    heading: 'Out of the chamber, into the argument',
  },
  {
    id: 'about',
    title: 'About',
    menuLabel: 'About Perspectiverse',
    subtitle: 'What this observatory is',
    eyebrow: 'About',
    heading: 'A week of talk, as a sky you can look around',
  },
  {
    id: 'author',
    title: 'The author',
    menuLabel: 'About the author',
    subtitle: AUTHOR_NAME,
    eyebrow: 'Author',
    heading: AUTHOR_NAME,
  },
  {
    id: 'connect',
    title: 'Connect',
    menuLabel: 'Connect',
    subtitle: 'GitHub, LinkedIn, and feedback',
    eyebrow: 'Connect',
    heading: 'Say hello',
  },
  {
    id: 'methodology',
    title: 'Methodology',
    menuLabel: 'Methodology',
    subtitle: 'How the sky is made',
    eyebrow: 'Methodology',
    heading: 'How the sky is made',
  },
  {
    id: 'faq',
    title: 'FAQ',
    menuLabel: 'FAQ',
    subtitle: 'Short answers',
    eyebrow: 'FAQ',
    heading: 'Questions people actually ask',
  },
  {
    id: 'donate',
    title: 'Donate',
    menuLabel: 'Donate',
    subtitle: 'Keep the sky public',
    eyebrow: 'Donate',
    heading: 'Keep this observatory public',
  },
]

const PAGE_IDS = new Set(SITE_PAGES.map((page) => page.id))

export function isSitePage(id) {
  return typeof id === 'string' && PAGE_IDS.has(id)
}

export function pageById(id) {
  return SITE_PAGES.find((page) => page.id === id) ?? null
}

export function neighborPages(id) {
  const index = SITE_PAGES.findIndex((page) => page.id === id)
  if (index < 0) return { prev: null, next: null }
  return {
    prev: SITE_PAGES[index - 1] ?? null,
    next: SITE_PAGES[index + 1] ?? null,
  }
}
