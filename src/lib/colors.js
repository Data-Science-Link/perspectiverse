import { SOLAR_BODIES } from './planets.js'

export const TOPIC_COLORS = Object.fromEntries(
  SOLAR_BODIES.map((body, index) => [index + 1, body.color]),
)

// Brand suite, always loudest → quietest. Gold is the primary opinion.
export const PERSPECTIVE_COLORS = [
  '#f4c14e',
  '#ff7a3d',
  '#6ea8ff',
  '#c77dff',
  '#2fd2a8',
  '#ff6b9d',
]

export const SPIKE_COLORS = PERSPECTIVE_COLORS

export function topicColor(topicId, body) {
  if (body?.color) return body.color
  return TOPIC_COLORS[topicId] ?? '#9aa3b5'
}

export function spikeColor(rank) {
  return PERSPECTIVE_COLORS[rank % PERSPECTIVE_COLORS.length]
}

export function rankPerspectives(perspectives = []) {
  return [...perspectives].sort((a, b) => {
    const delta = (b.volume_percent ?? 0) - (a.volume_percent ?? 0)
    if (delta !== 0) return delta
    return String(a.id).localeCompare(String(b.id))
  })
}

export function perspectiveRank(perspectives, perspectiveId) {
  return rankPerspectives(perspectives).findIndex((item) => item.id === perspectiveId)
}

export function hexToRgba(hex, alpha = 1) {
  const normalized = (hex ?? '#9aa3b5').replace('#', '')
  const value = normalized.length === 3
    ? normalized.split('').map((part) => part + part).join('')
    : normalized
  const int = Number.parseInt(value, 16)
  if (!Number.isFinite(int)) return `rgba(154, 163, 181, ${alpha})`
  const r = (int >> 16) & 255
  const g = (int >> 8) & 255
  const b = int & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
