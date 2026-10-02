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

export const PERSPECTIVE_COLOR_NAMES = ['Gold', 'Ember', 'Azure', 'Violet', 'Jade', 'Rose']

export function topicColor(topicId, body) {
  if (body?.color) return body.color
  return TOPIC_COLORS[topicId] ?? '#9aa3b5'
}

export function spikeColor(rank) {
  return PERSPECTIVE_COLORS[rank % PERSPECTIVE_COLORS.length]
}

function parseHex(hex) {
  const normalized = (hex ?? '#9aa3b5').replace('#', '')
  const value = normalized.length === 3
    ? normalized.split('').map((part) => part + part).join('')
    : normalized
  const int = Number.parseInt(value, 16)
  if (!Number.isFinite(int) || value.length !== 6) return [154, 163, 181]
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255]
}

function formatHex(channels) {
  return `#${channels.map((channel) => Math.round(Math.min(255, Math.max(0, channel))).toString(16).padStart(2, '0')).join('')}`
}

export function shadeHex(hex, factor = 0.55) {
  const [r, g, b] = parseHex(hex)
  return formatHex([r * factor, g * factor, b * factor])
}

export function mixHex(hex, other, amount = 0.5) {
  const blend = Math.min(1, Math.max(0, amount))
  const from = parseHex(hex)
  const to = parseHex(other)
  return formatHex(from.map((channel, index) => channel + (to[index] - channel) * blend))
}

const MAJORITY_SHADE = 0.32
const MINORITY_LIGHTEN = 0.62

export function faceShade(hex, rank, count) {
  const pigment = hex || '#9aa3b5'
  const faces = Math.max(1, Math.round(Number(count) || 1))
  const index = Math.min(Math.max(0, Math.round(Number(rank) || 0)), faces - 1)
  if (faces === 1) return shadeHex(pigment, MAJORITY_SHADE)
  const middle = (faces - 1) / 2
  if (index <= middle) {
    const towardPlanet = middle === 0 ? 1 : index / middle
    return shadeHex(pigment, MAJORITY_SHADE + (1 - MAJORITY_SHADE) * towardPlanet)
  }
  const span = faces - 1 - middle
  const towardLight = span === 0 ? 1 : (index - middle) / span
  return mixHex(pigment, '#ffffff', MINORITY_LIGHTEN * towardLight)
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
