export const SINGLE_VIEW_NOTE = 'No clear opposing view found in this sample'
export const STANCE_CHECK_FAILED = 'stance check failed'
export const PERSPECTIVES_PENDING = 'Perspectives still being analyzed'

export function oneViewNote(topic) {
  if (topic && topic.stance_check === STANCE_CHECK_FAILED) return PERSPECTIVES_PENDING
  if (topic && topic.opposing_note) return topic.opposing_note
  return SINGLE_VIEW_NOTE
}

export function showStanceFailure(topic) {
  return Boolean(topic && topic.stance_check === STANCE_CHECK_FAILED)
}

export const SITE_TITLE = 'Perspectiverse'
export const SITE_TAGLINE = 'See every perspective — and where yours stands.'
export const SOLAR_SYSTEM_LABEL = 'Filter topics'
export const WELCOME_STORAGE_KEY = 'perspectiverse.hide-welcome'

export function isWelcomeHidden() {
  try {
    return window.localStorage.getItem(WELCOME_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function setWelcomeHidden(hidden) {
  try {
    if (hidden) window.localStorage.setItem(WELCOME_STORAGE_KEY, '1')
    else window.localStorage.removeItem(WELCOME_STORAGE_KEY)
  } catch {
    // Private mode or disabled storage should never block the solar system.
  }
}
