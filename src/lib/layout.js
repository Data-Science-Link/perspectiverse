export const PLANET_MESH_RADIUS = 0.95
export const SUN_HALO_RADIUS = 1.08
export const SATURN_RING_RADIUS = 1.72
export const ORBIT_CLEARANCE = 0.72
const LABEL_PAD = 2.6

export function topicScale(volumePercent, skyMaxPercent = 100) {
  const relative = Math.max(0, Number(volumePercent) || 0) / Math.max(Number(skyMaxPercent) || 0, 0.01)
  return 0.4 + Math.min(relative, 1) * 1.7
}

export function bodyExtent(scale, { sun = false, rings = false } = {}) {
  let radius = Math.max(0, Number(scale) || 0) * PLANET_MESH_RADIUS
  if (sun) radius = Math.max(radius, scale * SUN_HALO_RADIUS)
  if (rings) radius = Math.max(radius, scale * SATURN_RING_RADIUS)
  return radius
}

function fallbackOrbitRadius(index) {
  return 4.4 + index * 2.6
}

export function orbitRadius(index, isSun) {
  if (isSun) return 0
  return fallbackOrbitRadius(index)
}

export function layoutSky(topics = [], volumeMax = 100) {
  const items = topics.map((topic, index) => {
    const scale = topicScale(topic.total_volume_percent, volumeMax)
    const sun = index === 0 || topic.body?.key === 'sun'
    const rings = Boolean(topic.body?.rings)
    return {
      scale,
      extent: bodyExtent(scale, { sun, rings }),
      sun,
      rings,
    }
  })

  const radii = []
  let lane = 0
  for (let i = 0; i < items.length; i += 1) {
    if (i === 0) {
      radii.push(0)
      lane = items[i].extent + ORBIT_CLEARANCE
      continue
    }
    const radius = lane + items[i].extent
    radii.push(radius)
    lane = radius + items[i].extent + ORBIT_CLEARANCE
  }

  const outerIndex = Math.max(items.length - 1, 0)
  const outerRadius = radii[outerIndex] ?? 0
  const outerExtent = items[outerIndex]?.extent ?? 0
  return {
    items,
    radii,
    extent: outerRadius + outerExtent + LABEL_PAD,
  }
}

export function orbitsClear(layout) {
  const { items = [], radii = [] } = layout ?? {}
  for (let i = 0; i < items.length; i += 1) {
    for (let j = i + 1; j < items.length; j += 1) {
      const gap = Math.abs((radii[j] ?? 0) - (radii[i] ?? 0)) - items[i].extent - items[j].extent
      if (gap < ORBIT_CLEARANCE - 1e-6) return false
    }
  }
  return true
}

export function systemExtent(planetCount = 10, layoutExtent = null) {
  if (layoutExtent != null) return layoutExtent
  const outerIndex = Math.max(1, Number(planetCount) - 1)
  return orbitRadius(outerIndex, false) + SUN_HALO_RADIUS * 2.3 + LABEL_PAD
}

export function homeLookAt(isMobile = false, planetCount = 10, layoutExtent = null) {
  const extent = systemExtent(planetCount, layoutExtent)
  const fov = isMobile ? 48 : 42
  const half = (fov * Math.PI) / 360
  const distance = (extent / Math.sin(half)) * (isMobile ? 1.16 : 1.08)
  const y = distance * (isMobile ? 0.38 : 0.44)
  const z = Math.sqrt(Math.max(distance * distance - y * y, 1))
  return [0, y, z, 0, 0, 0]
}

export function homeMaxDistance(isMobile = false, planetCount = 10, layoutExtent = null) {
  const [x, y, z] = homeLookAt(isMobile, planetCount, layoutExtent)
  return Math.hypot(x, y, z) * 1.4
}

function unitHash(seed) {
  const n = Math.sin(seed * 127.1 + 311.7) * 43758.5453123
  return n - Math.floor(n)
}

function seedFrom(id, index) {
  const text = String(id ?? index)
  let hash = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0) + index * 97
}

export function orbitElements(index, isSun, id, radius = null) {
  if (isSun) {
    return { radius: 0, speed: 0, inclination: 0, node: 0, phase: 0 }
  }

  const seed = seedFrom(id, index)
  const kepler = 0.105 / Math.sqrt(index + 1.55)
  const speedScale = 0.58 + unitHash(seed + 11) * 1.05
  const direction = unitHash(seed + 23) >= 0.5 ? 1 : -1
  const tiltSign = unitHash(seed + 37) >= 0.5 ? 1 : -1
  const inclination = tiltSign * (0.08 + unitHash(seed + 41) * 0.14)
  const node = (index * 2.399963229) + unitHash(seed + 53) * 0.4
  const phase = (index * 2.399963229) + unitHash(seed + 67) * 0.5

  return {
    radius: radius ?? orbitRadius(index, false),
    speed: kepler * speedScale * direction,
    inclination,
    node,
    phase,
  }
}

export function setOrbitPosition(target, radius, angle, inclination, node) {
  const cosT = Math.cos(angle)
  const sinT = Math.sin(angle)
  const cosO = Math.cos(node)
  const sinO = Math.sin(node)
  const cosI = Math.cos(inclination)
  const sinI = Math.sin(inclination)
  target.set(
    radius * (cosO * cosT - sinO * sinT * cosI),
    radius * (sinT * sinI),
    radius * (sinO * cosT + cosO * sinT * cosI),
  )
  return target
}

export function cameraOffsetForScale(scale) {
  return 3.4 + scale * 1.7
}

export function formatNumber(value) {
  return new Intl.NumberFormat('en-US').format(value)
}

export function formatPercent(value) {
  return `${Number(value).toFixed(1)}%`
}

export function sortPosts(posts = []) {
  return [...posts].sort((a, b) => (b.likes ?? 0) - (a.likes ?? 0))
}
