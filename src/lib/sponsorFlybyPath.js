import { Vector3 } from 'three'

/** Mid-depth arc between the sun and the home camera — never hugs the lens. */
export function sponsorFlightPath(t) {
  const x = -32 + t * 64
  const y = 8 + Math.sin(t * Math.PI) * 2.5
  const z = 28 + Math.cos(t * Math.PI) * 6
  return new Vector3(x, y, z)
}

/** Fly across the linear row/grid volume in front of the camera. */
export function sponsorFlightPathLinear(t, extentX = 14, extentY = 6) {
  const spanX = Math.max(8, extentX * 1.65)
  const x = -spanX * 0.5 + t * spanX
  const y = Math.sin(t * Math.PI) * Math.max(0.8, extentY * 0.22)
  const z = 1.8 + Math.cos(t * Math.PI) * 0.9
  return new Vector3(x, y, z)
}

export const SPONSOR_FLIGHT_SECONDS = 16
export const SPONSOR_IDLE_MIN_SECONDS = 50
export const SPONSOR_IDLE_MAX_SECONDS = 95
export const SPONSOR_TEST_FLIGHT_PROGRESS = 0.5

export function sponsorFlybyQueryMode() {
  if (typeof window === 'undefined') {
    return { enabled: false, animate: false, pin: false, pinProgress: SPONSOR_TEST_FLIGHT_PROGRESS }
  }
  const params = new URLSearchParams(window.location.search)
  const value = params.get('sponsorFlyby')
  if (!value) {
    return { enabled: false, animate: false, pin: false, pinProgress: SPONSOR_TEST_FLIGHT_PROGRESS }
  }
  const progressParam = params.get('sponsorProgress')
  const pinProgress = progressParam != null && progressParam !== ''
    ? Math.min(1, Math.max(0, Number.parseFloat(progressParam)))
    : SPONSOR_TEST_FLIGHT_PROGRESS
  return {
    enabled: true,
    animate: value === 'animate',
    pin: value !== 'animate',
    pinProgress: Number.isFinite(pinProgress) ? pinProgress : SPONSOR_TEST_FLIGHT_PROGRESS,
  }
}

/** @deprecated use sponsorFlybyQueryMode */
export function sponsorFlybyTestLoop() {
  return sponsorFlybyQueryMode().enabled
}
