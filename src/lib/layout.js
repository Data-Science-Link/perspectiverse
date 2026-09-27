export function topicScale(volumePercent) {
  return 0.42 + (volumePercent / 100) * 3.35
}

export function orbitRadius(index, isSun) {
  if (isSun) return 0
  return 3.8 + index * 1.22
}

export function orbitSpeed(index, isSun) {
  if (isSun) return 0
  return 0.13 / Math.sqrt(index + 2.2)
}

export function orbitInclination(index, isSun) {
  if (isSun) return 0
  return index % 2 === 0 ? 0.09 : -0.07
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
