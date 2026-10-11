export function morePostsLabel(hiddenCount, expanded = false) {
  if (expanded) return 'Show fewer posts'
  const count = Math.max(0, Number(hiddenCount) || 0)
  const noun = count === 1 ? 'post' : 'posts'
  return `Show ${count} more ${noun}`
}
