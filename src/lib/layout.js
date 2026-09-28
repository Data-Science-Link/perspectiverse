export function topicScale(volumePercent) {
  return 0.42 + (volumePercent / 100) * 3.35
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

export function orbitRadius(index, isSun) {
  if (isSun) return 0
  return 3.8 + index * 1.22
}

export function orbitElements(index, isSun, id) {
  if (isSun) {
    return { radius: 0, speed: 0, inclination: 0, node: 0, phase: 0 }
  }

  const seed = seedFrom(id, index)
  const radius = orbitRadius(index, false)
  const kepler = 0.105 / Math.sqrt(index + 1.55)
  const speedScale = 0.58 + unitHash(seed + 11) * 1.05
  const direction = unitHash(seed + 23) >= 0.5 ? 1 : -1
  const tiltSign = unitHash(seed + 37) >= 0.5 ? 1 : -1
  const inclination = tiltSign * (0.18 + unitHash(seed + 41) * 0.36)
  const node = unitHash(seed + 53) * Math.PI * 2
  const phase = unitHash(seed + 67) * Math.PI * 2

  return {
    radius,
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
