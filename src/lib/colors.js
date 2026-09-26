export const TOPIC_COLORS = {
  1: '#f4c14e',
  2: '#f27a45',
  3: '#3ecf9a',
  4: '#5b9dff',
  5: '#e15b7a',
  6: '#b07cff',
  7: '#3fd0e8',
  8: '#e8d36a',
  9: '#6ee07a',
  10: '#c9a2ff',
}

export const SPIKE_COLORS = ['#ffe08a', '#ff8b5c', '#7ee0c2', '#7eb6ff', '#f08ab0', '#d2b0ff']

export function topicColor(topicId) {
  return TOPIC_COLORS[topicId] ?? '#9aa3b5'
}

export function spikeColor(index) {
  return SPIKE_COLORS[index % SPIKE_COLORS.length]
}

export function hexToRgba(hex, alpha = 1) {
  const normalized = hex.replace('#', '')
  const value = normalized.length === 3
    ? normalized.split('').map((part) => part + part).join('')
    : normalized
  const int = Number.parseInt(value, 16)
  const r = (int >> 16) & 255
  const g = (int >> 8) & 255
  const b = int & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
