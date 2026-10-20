import { PerspectiveCamera, Vector3 } from 'three'
import { orbitElements, resumeOrbitAngle, setOrbitPosition } from './layout.js'
import { orbitLabelCssBox } from './orbitLabels.js'

/** @typedef {{ position: [number, number, number], target: [number, number, number], distance: number }} SolarView */
/** @typedef {{ minDistance?: number, maxDistance?: number, home?: number[], extent?: number, linear?: boolean, grid?: boolean }} SolarLimits */

const _pos = new Vector3()
const _target = new Vector3()
const _offset = new Vector3()
const _fitCamera = new PerspectiveCamera(48, 1, 0.1, 800)
const _fitPoint = new Vector3()

/** @type {{ key: string | null, view: SolarView | null, atHome: boolean }} */
let _stash = { key: null, view: null, atHome: false }

const HOME_POSE_TOLERANCE = 0.2

function poseMatchesHome(view, home, tolerance = HOME_POSE_TOLERANCE) {
  if (!view?.position || !view?.target || !Array.isArray(home) || home.length < 6) return false
  const homeDistance = Math.hypot(home[0] - home[3], home[1] - home[4], home[2] - home[5])
  if (Math.abs(view.distance - homeDistance) > tolerance) return false
  for (let i = 0; i < 3; i += 1) {
    if (Math.abs(view.position[i] - home[i]) > tolerance) return false
    if (Math.abs(view.target[i] - home[i + 3]) > tolerance) return false
  }
  return true
}

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
const MOBILE_ORBIT_MARGIN = 10
const _centroid = new Vector3()
const _focus = new Vector3()
const _camPos = new Vector3()
const _aim = new Vector3()
const _right = new Vector3()
const _up = new Vector3()

/**
 * World positions of the planets and their label anchors at the angles they
 * hold right now. The phone camera frames this cluster, not the full orbits.
 */
export function orbitSamplePoints(topics = [], layout = {}) {
  const radii = layout.radii ?? []
  const items = layout.items ?? []
  const point = new Vector3()
  return topics.map((topic, index) => {
    const isSun = index === 0
    const orbit = orbitElements(index, isSun, topic.id, radii[index] ?? 0)
    const angle = resumeOrbitAngle(topic.id, orbit.phase)
    if (isSun) point.set(0, 0, 0)
    else setOrbitPosition(point, orbit.radius, angle, orbit.inclination, orbit.node)
    const scale = items[index]?.scale ?? 1
    return {
      planet: [point.x, point.y, point.z],
      label: [point.x, point.y + scale * 1.32, point.z],
      bodyRadius: items[index]?.extent ?? scale,
      name: topic.name || 'Topic',
    }
  })
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

function usableBox(frame) {
  const width = Math.max(40, Number(frame.width) || 390)
  const height = Math.max(40, Number(frame.height) || 700)
  const usable = frame.usable ?? { x: 8, y: 8, width: width - 16, height: Math.max(40, height - 140) }
  const margin = Number.isFinite(frame.margin) ? frame.margin : MOBILE_ORBIT_MARGIN
  const box = {
    left: usable.x + margin,
    right: usable.x + usable.width - margin,
    top: usable.y + margin,
    bottom: usable.y + usable.height - margin,
  }
  if (!(box.right > box.left + 24)) {
    const mid = usable.x + usable.width / 2
    box.left = mid - 12
    box.right = mid + 12
  }
  if (!(box.bottom > box.top + 24)) {
    const mid = usable.y + usable.height / 2
    box.top = mid - 12
    box.bottom = mid + 12
  }
  return { width, height, box }
}

function contentBounds(samples, position, target, width, height) {
  const lookAt = [position.x, position.y, position.z, target.x, target.y, target.z]
  const half = (MOBILE_ORBIT_FOV * Math.PI) / 360
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const sample of samples) {
    const label = projectToCanvas(sample.label, lookAt, width, height)
    const planet = projectToCanvas(sample.planet, lookAt, width, height)
    if (!label || !planet || label.behind || planet.behind) return null
    const distP = Math.hypot(
      position.x - sample.planet[0],
      position.y - sample.planet[1],
      position.z - sample.planet[2],
    )
    const px = height / (2 * Math.tan(half) * Math.max(distP, 0.5))
    const br = (sample.bodyRadius || 0) * px
    const hw = (sample.labelWidth || 0) / 2
    const hh = (sample.labelHeight || 0) / 2
    minX = Math.min(minX, label.x - hw, planet.x - br)
    maxX = Math.max(maxX, label.x + hw, planet.x + br)
    minY = Math.min(minY, label.y - hh, planet.y - br)
    maxY = Math.max(maxY, label.y + hh, planet.y + br)
  }
  if (!Number.isFinite(minX)) return null
  return { minX, maxX, minY, maxY }
}

function boundsFit(bounds, box) {
  return Boolean(bounds)
    && bounds.minX >= box.left
    && bounds.maxX <= box.right
    && bounds.minY >= box.top
    && bounds.maxY <= box.bottom
}

function frameAt(samples, centroid, distance, azimuth, width, height, box) {
  const elevCos = Math.sqrt(Math.max(1 - MOBILE_ORBIT_ELEVATION * MOBILE_ORBIT_ELEVATION, 0.2))
  _aim.set(
    Math.sin(azimuth) * elevCos,
    MOBILE_ORBIT_ELEVATION,
    Math.cos(azimuth) * elevCos,
  ).multiplyScalar(distance)
  _focus.copy(centroid)
  let bounds = null
  const half = (MOBILE_ORBIT_FOV * Math.PI) / 360
  const pxPer = height / (2 * Math.tan(half) * distance)
  for (let step = 0; step < 6; step += 1) {
    _camPos.copy(_focus).add(_aim)
    bounds = contentBounds(samples, _camPos, _focus, width, height)
    if (!bounds) return null
    const dx = (box.left + box.right) / 2 - (bounds.minX + bounds.maxX) / 2
    const dy = (box.top + box.bottom) / 2 - (bounds.minY + bounds.maxY) / 2
    if (Math.abs(dx) < 0.6 && Math.abs(dy) < 0.6) break
    _fitCamera.fov = MOBILE_ORBIT_FOV
    _fitCamera.aspect = width / Math.max(height, 1)
    _fitCamera.position.copy(_camPos)
    _fitCamera.lookAt(_focus)
    _fitCamera.updateMatrixWorld()
    _right.setFromMatrixColumn(_fitCamera.matrixWorld, 0)
    _up.setFromMatrixColumn(_fitCamera.matrixWorld, 1)
    _focus.addScaledVector(_right, -dx / pxPer)
    _focus.addScaledVector(_up, dy / pxPer)
  }
  _camPos.copy(_focus).add(_aim)
  bounds = contentBounds(samples, _camPos, _focus, width, height)
  if (!bounds) return null
  return {
    bounds,
    lookAt: [_camPos.x, _camPos.y, _camPos.z, _focus.x, _focus.y, _focus.z],
    distance,
  }
}

/**
 * Phone Orbits camera. Frame the planets' current positions and their label
 * boxes inside the canvas area above the topic filter. A modest margin, and
 * the closest viewpoint that still fits, so the cluster fills that area.
 * Full orbit extents are not part of the fit.
 */
export function mobileOrbitHome(extent, frame = {}, options = {}) {
  const { width, height, box } = usableBox(frame)
  const samples = (options.samples ?? []).map((sample) => {
    if (sample.labelWidth && sample.labelHeight) return sample
    const css = orbitLabelCssBox(sample.name, width)
    return { ...sample, labelWidth: css.width, labelHeight: css.height }
  })
  const radius = Math.max(1, Number(extent) || 1)
  const referenceDistance = Number(options.referenceDistance)
  const baseDistanceFactor = Number(options.baseDistanceFactor) || 16
  if (samples.length === 0) {
    const distance = referenceDistance > 1 ? referenceDistance : radius * 2.5
    const lift = distance * MOBILE_ORBIT_ELEVATION
    const z = Math.sqrt(Math.max(distance * distance - lift * lift, 1))
    return {
      lookAt: [0, lift, z, 0, 0, 0],
      labelDistanceFactor: baseDistanceFactor,
      distance,
    }
  }

  _centroid.set(0, 0, 0)
  for (const sample of samples) {
    _centroid.x += sample.planet[0]
    _centroid.y += sample.planet[1]
    _centroid.z += sample.planet[2]
  }
  _centroid.multiplyScalar(1 / samples.length)

  let lo = Math.max(6, radius * 0.35)
  let hi = Math.max(lo + 4, radius * 8)
  let best = null
  const steps = 16
  for (let index = 0; index < steps; index += 1) {
    const azimuth = (index / steps) * Math.PI * 2
    let near = lo
    let far = hi
    let fitting = null
    for (let step = 0; step < 14; step += 1) {
      const distance = (near + far) / 2
      const framed = frameAt(samples, _centroid, distance, azimuth, width, height, box)
      if (framed && boundsFit(framed.bounds, box)) {
        fitting = framed
        far = distance
      } else {
        near = distance
      }
    }
    if (!fitting) continue
    const spanX = fitting.bounds.maxX - fitting.bounds.minX
    const spanY = fitting.bounds.maxY - fitting.bounds.minY
    const area = (spanX / Math.max(box.right - box.left, 1)) * (spanY / Math.max(box.bottom - box.top, 1))
    if (!best || fitting.distance < best.distance - 0.4 || (Math.abs(fitting.distance - best.distance) <= 0.4 && area > best.area)) {
      best = { ...fitting, area }
    }
  }

  const pose = best ?? frameAt(samples, _centroid, hi, 0, width, height, box)
  const distance = pose?.distance ?? hi
  const lookAt = pose?.lookAt ?? [0, distance * MOBILE_ORBIT_ELEVATION, distance, ..._centroid.toArray()]
  return {
    lookAt,
    labelDistanceFactor: baseDistanceFactor,
    distance,
    bounds: pose?.bounds ?? null,
  }
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

export function stashSolarView(controls, layoutKey, limits) {
  if (!layoutKey) return null
  const snapshot = readCameraLookAt(controls)
  if (!snapshot) return null
  _stash = {
    key: layoutKey,
    view: snapshot,
    // Phone orbit home is recomputed from the planets' current angles. Keeping
    // a stash that was still that home pose would restore the old framing and
    // leave the orbit labels unplaced.
    atHome: poseMatchesHome(snapshot, limits?.home),
  }
  return snapshot
}

export function peekSolarView() {
  return _stash.view
}

export function peekSolarLayoutKey() {
  return _stash.key
}

export function clearSolarView() {
  _stash = { key: null, view: null, atHome: false }
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
  if (_stash.atHome) return false
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
    stash: () => stashSolarView(getControls(), getContext()?.layoutKey, getContext()?.limits),
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
