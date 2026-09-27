import { SOLAR_BODIES } from './planets'

export const TOPIC_COLORS = Object.fromEntries(
  SOLAR_BODIES.map((body, index) => [index + 1, body.color]),
)

export const SPIKE_COLORS = ['#ffe08a', '#ff8b5c', '#7ee0c2', '#7eb6ff', '#f08ab0', '#d2b0ff']

export function topicColor(topicId, body) {
  if (body?.color) return body.color
  return TOPIC_COLORS[topicId] ?? '#9aa3b5'
}

export function spikeColor(index) {
  return SPIKE_COLORS[index % SPIKE_COLORS.length]
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
