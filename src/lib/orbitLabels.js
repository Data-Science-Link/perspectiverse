function clampNudge(item, bounds) {
  const left = item.x + item.nx
  const top = item.y + item.ny
  if (left < bounds.left) item.nx += bounds.left - left
  if (left + item.w > bounds.right) item.nx -= (left + item.w) - bounds.right
  if (top < bounds.top) item.ny += bounds.top - top
  if (top + item.h > bounds.bottom) item.ny -= (top + item.h) - bounds.bottom
}

/**
 * Push label boxes apart so each center stays on its own pill, and keep
 * them inside the usable screen rect. `boxes` are un-nudged top-left rects.
 * Returns one {x, y} nudge per box. Running it again on the same bases
 * returns the same nudges.
 */
export function separateLabelBoxes(boxes, bounds, { gap = 3, iterations = 24 } = {}) {
  const items = boxes.map((box) => ({
    x: box.x,
    y: box.y,
    w: Math.max(1, box.w),
    h: Math.max(1, box.h),
    nx: 0,
    ny: 0,
  }))
  if (!bounds) return items.map(() => ({ x: 0, y: 0 }))

  for (let iter = 0; iter < iterations; iter += 1) {
    for (let i = 0; i < items.length; i += 1) {
      for (let j = i + 1; j < items.length; j += 1) {
        const a = items[i]
        const b = items[j]
        const ax = a.x + a.nx
        const ay = a.y + a.ny
        const bx = b.x + b.nx
        const by = b.y + b.ny
        const overlapX = Math.min(ax + a.w, bx + b.w) + gap - Math.max(ax, bx)
        const overlapY = Math.min(ay + a.h, by + b.h) + gap - Math.max(ay, by)
        if (overlapX <= 0 || overlapY <= 0) continue
        const acx = ax + a.w / 2
        const acy = ay + a.h / 2
        const bcx = bx + b.w / 2
        const bcy = by + b.h / 2
        if (overlapX < overlapY) {
          const sign = acx >= bcx ? 1 : -1
          const push = overlapX / 2
          a.nx += sign * push
          b.nx -= sign * push
        } else {
          const sign = acy >= bcy ? 1 : -1
          const push = overlapY / 2
          a.ny += sign * push
          b.ny -= sign * push
        }
      }
    }
    for (const item of items) clampNudge(item, bounds)
  }

  return items.map((item) => ({
    x: Math.round(item.nx),
    y: Math.round(item.ny),
  }))
}

export function applyOrbitLabelNudges() {
  if (typeof document === 'undefined') return
  const nodes = [...document.querySelectorAll('.observatory .planet-label.is-mobile:not(.is-linear)')]
  if (nodes.length === 0) return
  const header = document.querySelector('header')?.getBoundingClientRect()
  const chrome = document.querySelector('.observatory-chrome')?.getBoundingClientRect()
  const bounds = {
    left: 4,
    top: Math.max(4, (header?.bottom ?? 0) + 4),
    right: window.innerWidth - 4,
    bottom: Math.max(40, (chrome?.top ?? window.innerHeight) - 4),
  }
  if (!(bounds.right > bounds.left + 40) || !(bounds.bottom > bounds.top + 40)) return
  const boxes = nodes.map((node) => {
    const nudge = node.__orbitNudge || { x: 0, y: 0 }
    const rect = node.getBoundingClientRect()
    return {
      x: rect.left - nudge.x,
      y: rect.top - nudge.y,
      w: rect.width,
      h: rect.height,
    }
  })
  const nudges = separateLabelBoxes(boxes, bounds)
  nodes.forEach((node, index) => {
    const next = nudges[index]
    const prev = node.__orbitNudge || { x: 0, y: 0 }
    if (prev.x === next.x && prev.y === next.y) return
    const rect = node.getBoundingClientRect()
    const layoutWidth = node.offsetWidth || rect.width
    const scale = layoutWidth > 0 ? rect.width / layoutWidth : 1
    const localX = scale > 0.05 ? next.x / scale : next.x
    const localY = scale > 0.05 ? next.y / scale : next.y
    node.__orbitNudge = next
    node.style.translate = next.x === 0 && next.y === 0
      ? ''
      : `${localX.toFixed(2)}px ${localY.toFixed(2)}px`
  })
}

export function clearOrbitLabelNudges() {
  if (typeof document === 'undefined') return
  document.querySelectorAll('.observatory .planet-label').forEach((node) => {
    if (node.__orbitNudge || node.style.translate) {
      node.style.translate = ''
      delete node.__orbitNudge
    }
  })
}

export function labelCenterIsClear(boxes) {
  return boxes.every((box, index) => {
    const cx = box.x + box.w / 2
    const cy = box.y + box.h / 2
    return boxes.every((other, otherIndex) => {
      if (otherIndex === index) return true
      return cx < other.x || cx > other.x + other.w || cy < other.y || cy > other.y + other.h
    })
  })
}
