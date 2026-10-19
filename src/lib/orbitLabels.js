export const ORBIT_LABEL_FONT_PX = 10

/** Screen size of a phone orbit pill before any nudge. Matches the overlay CSS. */
export function orbitLabelCssBox(name, viewportWidth = 390) {
  const text = String(name || 'Topic')
  const font = ORBIT_LABEL_FONT_PX
  const padX = 12
  const padY = 4
  const border = 2
  const natural = Math.ceil(text.length * font * 0.62 + padX + border)
  const cap = Math.max(64, viewportWidth * 0.46)
  return {
    width: Math.min(cap, Math.max(36, natural)),
    height: Math.ceil(font * 1.25 + padY + border),
  }
}

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
