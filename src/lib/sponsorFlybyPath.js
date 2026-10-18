import { Vector3 } from 'three'

/** Mid-depth arc between the sun and the home camera — never hugs the lens. */
export function sponsorFlightPath(t) {
  const x = -32 + t * 64
  const y = 8 + Math.sin(t * Math.PI) * 2.5
  const z = 28 + Math.cos(t * Math.PI) * 6
  return new Vector3(x, y, z)
}

export const SPONSOR_FLIGHT_SECONDS = 16
export const SPONSOR_IDLE_MIN_SECONDS = 50
export const SPONSOR_IDLE_MAX_SECONDS = 95
export const SPONSOR_TEST_FLIGHT_PROGRESS = 0.5

export function sponsorFlybyTestLoop() {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).has('sponsorFlyby')
}
