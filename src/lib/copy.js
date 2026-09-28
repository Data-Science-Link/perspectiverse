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
