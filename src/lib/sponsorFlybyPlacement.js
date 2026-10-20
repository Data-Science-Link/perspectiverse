export function rectsOverlap(a, b, minOverlap = 4) {
  const overlapW = Math.min(a.right, b.right) - Math.max(a.left, b.left)
  const overlapH = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
  return overlapW > minOverlap && overlapH > minOverlap
}

export function pillOpacityForLabels(pillRect, labelRects) {
  for (const labelRect of labelRects) {
    if (rectsOverlap(pillRect, labelRect)) return 0.22
  }
  return 1
}

export function towSideForShip(shipX, rowWidth, bounds, preferred = 'right', gap = 8) {
  const fitsRight = shipX + gap + rowWidth <= bounds.right
  const fitsLeft = shipX - gap - rowWidth >= bounds.left
  if (fitsRight && fitsLeft) return preferred
  if (fitsRight) return 'right'
  if (fitsLeft) return 'left'
  return preferred
}
