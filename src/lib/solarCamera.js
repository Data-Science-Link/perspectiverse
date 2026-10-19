import { PerspectiveCamera, Vector3 } from 'three'

/** @typedef {{ position: [number, number, number], target: [number, number, number], distance: number }} SolarView */
/** @typedef {{ minDistance?: number, maxDistance?: number, home?: number[], extent?: number, linear?: boolean, grid?: boolean }} SolarLimits */

const _pos = new Vector3()
const _target = new Vector3()
const _offset = new Vector3()
const _fitCamera = new PerspectiveCamera(48, 1, 0.1, 800)
const _fitPoint = new Vector3()

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

const MOBILE_ORBIT_FOV = 48
const MOBILE_ORBIT_ELEVATION = 0.26
const MOBILE_ORBIT_PAD_X = 48
const MOBILE_ORBIT_PAD_Y = 18

function orbitSphereSamples(radius) {
  const points = [[0, 0, 0]]
  const count = 42
  const golden = Math.PI * (3 - Math.sqrt(5))
  for (let index = 0; index < count; index += 1) {
    const y = count === 1 ? 0 : 1 - (index / (count - 1)) * 2
    const ring = Math.sqrt(Math.max(0, 1 - y * y))
    const theta = golden * index
    points.push([
      Math.cos(theta) * ring * radius,
      y * radius,
      Math.sin(theta) * ring * radius,
    ])
  }
  return points
}

function orbitPose(distance, targetY) {
  const lift = distance * MOBILE_ORBIT_ELEVATION
  const z = Math.sqrt(Math.max(distance * distance - lift * lift, 1))
  return {
    position: [0, targetY + lift, z],
    target: [0, targetY, 0],
  }
}

export function projectToCanvas(point, lookAt, width, height, fov = MOBILE_ORBIT_FOV) {
  if (!lookAt || lookAt.length < 6) return null
  _fitCamera.fov = fov
  _fitCamera.aspect = width / Math.max(height, 1)
  _fitCamera.position.set(lookAt[0], lookAt[1], lookAt[2])
  _fitCamera.lookAt(lookAt[3], lookAt[4], lookAt[5])
  _fitCamera.updateProjectionMatrix()
  _fitCamera.updateMatrixWorld()
  _fitPoint.set(point[0], point[1], point[2]).project(_fitCamera)
  return {
    x: (_fitPoint.x * 0.5 + 0.5) * width,
    y: (1 - _fitPoint.y) * 0.5 * height,
    behind: _fitPoint.z < -1 || _fitPoint.z > 1,
  }
}

function projectBounds(samples, pose, width, height) {
  const lookAt = [...pose.position, ...pose.target]
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  let behind = false
  for (const point of samples) {
    const projected = projectToCanvas(point, lookAt, width, height)
    if (!projected || projected.behind) behind = true
    if (!projected) continue
    minX = Math.min(minX, projected.x)
    maxX = Math.max(maxX, projected.x)
    minY = Math.min(minY, projected.y)
    maxY = Math.max(maxY, projected.y)
  }
  return { minX, maxX, minY, maxY, behind }
}

function boundsFit(bounds, box) {
  return !bounds.behind
    && bounds.minX >= box.left
    && bounds.maxX <= box.right
    && bounds.minY >= box.top
    && bounds.maxY <= box.bottom
}

function centerTargetY(distance, samples, width, height, box) {
  const want = (box.top + box.bottom) / 2
  let lo = -distance
  let hi = distance
  let best = 0
  for (let step = 0; step < 22; step += 1) {
    const mid = (lo + hi) / 2
    const bounds = projectBounds(samples, orbitPose(distance, mid), width, height)
    const center = (bounds.minY + bounds.maxY) / 2
    best = mid
    if (!Number.isFinite(center) || center < want) lo = mid
    else hi = mid
  }
  return best
}

/**
 * Phone Orbits camera. The vertical-only home distance fits a desktop-shaped
 * view; on a 390-wide portrait the orbital disk runs off both sides, and on a
 * short landscape the bottom of that disk sits under the topic filter.
 * Frame the whole disk inside the canvas area above that chrome.
 */
export function mobileOrbitHome(extent, frame = {}, options = {}) {
  const radius = Math.max(1, Number(extent) || 1)
  const width = Math.max(40, Number(frame.width) || 390)
  const height = Math.max(40, Number(frame.height) || 700)
  const usable = frame.usable ?? { x: 8, y: 8, width: width - 16, height: Math.max(40, height - 140) }
  const padX = Math.min(
    Number.isFinite(frame.padX) ? frame.padX : MOBILE_ORBIT_PAD_X,
    Math.max(8, usable.width * 0.24),
  )
  const padY = Math.min(
    Number.isFinite(frame.padY) ? frame.padY : MOBILE_ORBIT_PAD_Y,
    Math.max(6, usable.height * 0.16),
  )
  const box = {
    left: usable.x + padX,
    right: usable.x + usable.width - padX,
    top: usable.y + padY,
    bottom: usable.y + usable.height - padY,
  }
  if (!(box.right > box.left + 16)) {
    const mid = usable.x + usable.width / 2
    box.left = mid - 8
    box.right = mid + 8
  }
  if (!(box.bottom > box.top + 16)) {
    const mid = usable.y + usable.height / 2
    box.top = mid - 8
    box.bottom = mid + 8
  }

  const samples = orbitSphereSamples(radius)
  let lo = radius * 0.6
  let hi = radius * 16
  let fitting = null
  for (let step = 0; step < 24; step += 1) {
    const distance = (lo + hi) / 2
    const targetY = centerTargetY(distance, samples, width, height, box)
    const bounds = projectBounds(samples, orbitPose(distance, targetY), width, height)
    if (boundsFit(bounds, box)) {
      fitting = distance
      hi = distance
    } else {
      lo = distance
    }
  }
  const distance = (fitting ?? hi) * 1.04
  const targetY = centerTargetY(distance, samples, width, height, box)
  const pose = orbitPose(distance, targetY)
  const lookAt = [...pose.position, ...pose.target]
  const referenceDistance = Number(options.referenceDistance)
  const baseDistanceFactor = Number(options.baseDistanceFactor) || 16
  const labelDistanceFactor = referenceDistance > 1
    ? baseDistanceFactor * (distance / referenceDistance)
    : baseDistanceFactor
  return { lookAt, labelDistanceFactor, distance }
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
