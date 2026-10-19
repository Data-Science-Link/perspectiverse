import { Vector3 } from 'three'

/** @typedef {{ position: [number, number, number], target: [number, number, number], distance: number }} SolarView */
/** @typedef {{ minDistance?: number, maxDistance?: number, home?: number[], extent?: number, linear?: boolean, grid?: boolean }} SolarLimits */

const _pos = new Vector3()
const _target = new Vector3()
const _offset = new Vector3()

/** @type {{ key: string | null, view: SolarView | null }} */
let _stash = { key: null, view: null }

export const FREEZE_ORBITS_STORAGE_KEY = 'perspectiverse.freeze-orbits'

export function solarOrbitsFrozen() {
  return typeof window !== 'undefined' && window.localStorage?.getItem(FREEZE_ORBITS_STORAGE_KEY) === '1'
}

export function solarLayoutKey(category = 'all', linear = false, grid = false) {
  const topicFilter = category && category !== 'all' ? category : 'all'
  if (!linear) return `${topicFilter}:orbit`
  return `${topicFilter}:${grid ? 'grid' : 'linear'}`
}

export function homeDistanceFromLookAt(home = []) {
  if (home.length < 6) return null
  const [px, py, pz, tx, ty, tz] = home
  return Math.hypot(px - tx, py - ty, pz - tz)
}

export function readCameraLookAt(controls) {
  if (!controls?.getPosition || !controls.getTarget) return null
  controls.getPosition(_pos, true)
  controls.getTarget(_target, true)
  return {
    position: [_pos.x, _pos.y, _pos.z],
    target: [_target.x, _target.y, _target.z],
    distance: _pos.distanceTo(_target),
  }
}

export function clampSolarView(view, limits = {}) {
  if (!view?.position || !view?.target) return null
  const {
    minDistance = 3.2,
    maxDistance = Infinity,
    extent = 12,
    linear = false,
    grid = false,
  } = limits

  const target = new Vector3(...view.target)
  const linearMode = linear || grid
  const pan = extent * (linearMode ? 0.55 : 0.45)
  const panY = extent * (linearMode ? 0.35 : 0.3)
  const panZ = extent * (linearMode ? 0.25 : 0.45)
  target.x = Math.min(Math.max(target.x, -pan), pan)
  target.y = Math.min(Math.max(target.y, -panY), panY)
  target.z = Math.min(Math.max(target.z, -panZ), panZ)

  _offset.set(...view.position).sub(new Vector3(...view.target))
  let distance = _offset.length()
  if (distance < 1e-6) {
    _offset.set(0, 0, 1)
    distance = 1
  }
  distance = Math.min(Math.max(distance, minDistance), maxDistance)
  _offset.normalize().multiplyScalar(distance)
  const position = target.clone().add(_offset)

  return {
    position: [position.x, position.y, position.z],
    target: [target.x, target.y, target.z],
    distance,
  }
}

export function stashSolarView(controls, layoutKey) {
  if (!layoutKey) return null
  const snapshot = readCameraLookAt(controls)
  if (!snapshot) return null
  _stash = { key: layoutKey, view: snapshot }
  return snapshot
}

export function peekSolarView() {
  return _stash.view
}

export function peekSolarLayoutKey() {
  return _stash.key
}

export function clearSolarView() {
  _stash = { key: null, view: null }
}

export function applySolarView(controls, view, transition = false) {
  if (!controls || !view?.position || !view?.target) return false
  const [px, py, pz] = view.position
  const [tx, ty, tz] = view.target
  controls.setLookAt(px, py, pz, tx, ty, tz, transition)
  return true
}

export function restoreSolarView(controls, layoutKey, limits, transition = false) {
  if (!_stash.view || !_stash.key || _stash.key !== layoutKey) return false
  const clamped = clampSolarView(_stash.view, limits)
  if (!clamped) return false
  return applySolarView(controls, clamped, transition)
}

export function installSolarCameraTestHooks(getControls, getContext) {
  if (typeof window === 'undefined') return
  window.__PV_SOLAR_CAMERA__ = {
    read: () => readCameraLookAt(getControls()),
    peekStash: () => peekSolarView(),
    peekLayoutKey: () => peekSolarLayoutKey(),
    layoutKey: () => getContext()?.layoutKey ?? null,
    homeDistance: () => homeDistanceFromLookAt(getContext()?.limits?.home),
    limits: () => getContext()?.limits ?? null,
    stash: () => stashSolarView(getControls(), getContext()?.layoutKey),
    dolly: (amount = 0.45) => {
      const controls = getControls()
      if (controls?.dolly) controls.dolly(amount, true)
    },
    truck: (x = 0, y = 0) => {
      const controls = getControls()
      if (controls?.truck) controls.truck(x, y, true)
    },
  }
}
