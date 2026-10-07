export const PLANET_MESH_RADIUS = 0.95
export const SUN_HALO_RADIUS = 1.28
export const SATURN_RING_RADIUS = 1.72
export const ORBIT_CLEARANCE = 0.34
const LABEL_PAD = 1.35

export function topicScale(volumePercent, systemMaxPercent = 100) {
  const relative = Math.max(0, Number(volumePercent) || 0) / Math.max(Number(systemMaxPercent) || 0, 0.01)
  return 0.38 + Math.min(relative, 1) * 1.05
}

export function bodyExtent(scale, { sun = false, rings = false } = {}) {
  let radius = Math.max(0, Number(scale) || 0) * PLANET_MESH_RADIUS
  if (sun) radius = Math.max(radius, scale * SUN_HALO_RADIUS)
  if (rings) radius = Math.max(radius, scale * SATURN_RING_RADIUS)
  return radius
}

function fallbackOrbitRadius(index) {
  return 3.1 + index * 1.85
}

export function orbitRadius(index, isSun) {
  if (isSun) return 0
  return fallbackOrbitRadius(index)
}

export function layoutSolarSystem(topics = [], volumeMax = 100) {
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

export function layoutLinear(topics = [], volumeMax = 100) {
  const gap = 1.7
  const specs = topics.map((topic, index) => {
    const scale = topicScale(topic.total_volume_percent, volumeMax)
    const sun = index === 0 || topic.body?.key === 'sun'
    const rings = Boolean(topic.body?.rings)
    return { extent: bodyExtent(scale, { sun, rings }) }
  })
  let cursor = 0
  const centers = []
  for (const spec of specs) {
    centers.push(cursor + spec.extent)
    cursor += spec.extent * 2 + gap
  }
  const width = Math.max(cursor - gap, 0)
  const shift = width / 2
  const positions = centers.map((center) => [center - shift, 0, 0])
  return {
    positions,
    extent: width / 2 + LABEL_PAD,
    mode: 'linear',
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

export function homeLookAt(isMobile = false, planetCount = 10, layoutExtent = null, options = {}) {
  const extent = systemExtent(planetCount, layoutExtent)
  const fov = isMobile ? 48 : 42
  const half = (fov * Math.PI) / 360
  if (options.linear) {
    const aspect = isMobile ? 0.58 : 1.2
    const horizontalHalf = Math.atan(Math.tan(half) * aspect)
    const distance = (extent / Math.tan(horizontalHalf)) * (isMobile ? 1.12 : 1.06)
    const y = distance * 0.22
    const z = Math.sqrt(Math.max(distance * distance - y * y, 1))
    return [0, y, z, 0, 0, 0]
  }
  const distance = (extent / Math.sin(half)) * (isMobile ? 1.04 : 1.0)
  const y = distance * (isMobile ? 0.26 : 0.32)
  const z = Math.sqrt(Math.max(distance * distance - y * y, 1))
  return [0, y, z, 0, 0, 0]
}

export function homeMaxDistance(isMobile = false, planetCount = 10, layoutExtent = null, options = {}) {
  const [x, y, z] = homeLookAt(isMobile, planetCount, layoutExtent, options)
  return Math.hypot(x, y, z) * 1.35
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

function randomUnit(seedA, seedB) {
  const z = unitHash(seedA) * 2 - 1
  const theta = unitHash(seedB) * Math.PI * 2
  const radial = Math.sqrt(Math.max(1 - z * z, 0))
  return [radial * Math.cos(theta), z, radial * Math.sin(theta)]
}

export function orbitElements(index, isSun, id, radius = null) {
  if (isSun) {
    return { radius: 0, speed: 0, inclination: 0, node: 0, phase: 0 }
  }

  const seed = seedFrom(id, index)
  const kepler = 0.105 / Math.sqrt(index + 1.55)
  const speedScale = 0.58 + unitHash(seed + 11) * 1.05
  const direction = unitHash(seed + 23) >= 0.5 ? 1 : -1
  // Uniform random orbital plane: some sit near the equator, some near a right angle.
  const inclination = Math.acos(Math.min(1, Math.max(-1, 2 * unitHash(seed + 41) - 1)))
  const node = unitHash(seed + 53) * Math.PI * 2
  // Full-range random starting angle so planets are evenly distributed on first load.
  const phase = unitHash(seed + 67) * Math.PI * 2

  return {
    radius: radius ?? orbitRadius(index, false),
    speed: kepler * speedScale * direction,
    inclination,
    node,
    phase,
  }
}

// Module-level clock so planet orbital angles survive Observatory remounts (e.g. mobile
// navigate-to-reading → back). Keyed by topic id; cleared lazily via normal GC since topic
// sets are small and stable within a session.
const _orbitClock = new Map()

export function resumeOrbitAngle(id, initial) {
  return _orbitClock.has(id) ? _orbitClock.get(id) : initial
}

export function saveOrbitAngle(id, angle) {
  _orbitClock.set(id, angle)
}

export function bodySpin(id, index = 0) {
  const seed = seedFrom(id, index)
  const speed = 0.28 + unitHash(seed + 97) * 0.22
  return {
    axis: randomUnit(seed + 71, seed + 83),
    speed,
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

export function allocatePercents(weights = [], decimals = 1) {
  const count = weights.length
  if (count === 0) return []
  const scale = 10 ** decimals
  const target = 100 * scale
  const numeric = weights.map((value) => Math.max(0, Number(value) || 0))
  const total = numeric.reduce((sum, value) => sum + value, 0)
  if (total <= 0) {
    const even = Math.floor(target / count)
    const parts = Array.from({ length: count }, () => even)
    let leftover = target - even * count
    for (let index = 0; leftover > 0; index += 1, leftover -= 1) {
      parts[index % count] += 1
    }
    return parts.map((value) => value / scale)
  }

  const raw = numeric.map((value) => (value / total) * target)
  const floors = raw.map((value) => Math.floor(value + 1e-9))
  let remainder = target - floors.reduce((sum, value) => sum + value, 0)
  const order = raw
    .map((value, index) => ({ index, frac: value - floors[index] }))
    .sort((a, b) => b.frac - a.frac || a.index - b.index)
  const parts = floors.slice()
  for (let index = 0; index < remainder; index += 1) {
    parts[order[index % count].index] += 1
  }
  return parts.map((value) => value / scale)
}

export function withSharePercents(topics = []) {
  const shares = allocatePercents(topics.map((topic) => topic.total_volume_percent))
  return topics.map((topic, index) => {
    const perspectives = topic.perspectives ?? []
    const faceShares = perspectives.length
      ? allocatePercents(perspectives.map((face) => face.volume_percent))
      : []
    return {
      ...topic,
      total_volume_percent: shares[index],
      perspectives: perspectives.map((face, faceIndex) => ({
        ...face,
        volume_percent: faceShares[faceIndex],
      })),
    }
  })
}

export function sortPosts(posts = []) {
  return [...posts].sort((a, b) => {
    const aMatch = a.match == null ? null : Number(a.match)
    const bMatch = b.match == null ? null : Number(b.match)
    if (aMatch != null || bMatch != null) {
      const delta = (bMatch ?? -1) - (aMatch ?? -1)
      if (delta !== 0) return delta
    }
    return (b.likes ?? 0) - (a.likes ?? 0)
  })
}
