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
  item.nx = Math.round(item.nx)
  item.ny = Math.round(item.ny)
}

function overlapAmount(a, b, gap) {
  const ax = a.x + a.nx
  const ay = a.y + a.ny
  const bx = b.x + b.nx
  const by = b.y + b.ny
  return {
    x: Math.min(ax + a.w, bx + b.w) + gap - Math.max(ax, bx),
    y: Math.min(ay + a.h, by + b.h) + gap - Math.max(ay, by),
  }
}

function slackFor(item, bounds) {
  const left = item.x + item.nx
  const top = item.y + item.ny
  return {
    left: left - bounds.left,
    right: bounds.right - (left + item.w),
    top: top - bounds.top,
    bottom: bounds.bottom - (top + item.h),
  }
}

function insideBounds(item, bounds) {
  const slack = slackFor(item, bounds)
  return slack.left >= 0 && slack.right >= 0 && slack.top >= 0 && slack.bottom >= 0
}

function hitsOther(item, items, index, gap) {
  for (let other = 0; other < items.length; other += 1) {
    if (other === index) continue
    const overlap = overlapAmount(item, items[other], gap)
    if (overlap.x > 0 && overlap.y > 0) return true
  }
  return false
}

function pushApart(a, b, bounds, axis, amount) {
  const aCenter = axis === 'x'
    ? a.x + a.nx + a.w / 2
    : a.y + a.ny + a.h / 2
  const bCenter = axis === 'x'
    ? b.x + b.nx + b.w / 2
    : b.y + b.ny + b.h / 2
  const aPositive = aCenter >= bCenter
  const slackA = slackFor(a, bounds)
  const slackB = slackFor(b, bounds)
  const roomA = Math.max(0, axis === 'x'
    ? (aPositive ? slackA.right : slackA.left)
    : (aPositive ? slackA.bottom : slackA.top))
  const roomB = Math.max(0, axis === 'x'
    ? (aPositive ? slackB.left : slackB.right)
    : (aPositive ? slackB.top : slackB.bottom))
  let pushA = Math.ceil(amount / 2)
  let pushB = amount - pushA
  if (pushA > roomA) {
    pushB += pushA - roomA
    pushA = roomA
  }
  if (pushB > roomB) {
    pushA = Math.min(roomA, pushA + (pushB - roomB))
    pushB = roomB
  }
  const signA = aPositive ? 1 : -1
  if (axis === 'x') {
    a.nx += signA * pushA
    b.nx -= signA * pushB
  } else {
    a.ny += signA * pushA
    b.ny -= signA * pushB
  }
}

function squareRing(radius) {
  const points = []
  for (let dx = -radius; dx <= radius; dx += 2) {
    for (let dy = -radius; dy <= radius; dy += 2) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== radius) continue
      points.push([dx, dy])
    }
  }
  return points
}

function parkNearAnchor(item, items, index, bounds, gap) {
  const savedX = item.nx
  const savedY = item.ny
  const limit = Math.max(bounds.right - bounds.left, bounds.bottom - bounds.top, 40)
  for (let radius = 0; radius <= limit; radius += 2) {
    const points = radius === 0 ? [[0, 0]] : squareRing(radius)
    let best = null
    for (const [dx, dy] of points) {
      item.nx = dx
      item.ny = dy
      if (!insideBounds(item, bounds) || hitsOther(item, items, index, gap)) continue
      const score = dx * dx + dy * dy
      if (!best || score < best.score) best = { dx, dy, score }
    }
    if (best) {
      item.nx = best.dx
      item.ny = best.dy
      return true
    }
  }
  item.nx = savedX
  item.ny = savedY
  return false
}

/**
 * Push label boxes apart so no two pills intersect, and keep them inside the
 * usable screen rect. `boxes` are un-nudged top-left rects. Returns one
 * integer {x, y} nudge per box, applied as `round(box) + nudge`. The same
 * bases always return the same nudges. A label may leave its planet.
 */
export function separateLabelBoxes(boxes, bounds, { gap = 2, iterations = 48 } = {}) {
  const items = boxes.map((box) => ({
    x: Math.round(box.x),
    y: Math.round(box.y),
    w: Math.max(1, Math.round(box.w)),
    h: Math.max(1, Math.round(box.h)),
    nx: 0,
    ny: 0,
  }))
  if (!bounds) return items.map(() => ({ x: 0, y: 0 }))

  for (let iter = 0; iter < iterations; iter += 1) {
    let moved = false
    for (let i = 0; i < items.length; i += 1) {
      for (let j = i + 1; j < items.length; j += 1) {
        const overlap = overlapAmount(items[i], items[j], gap)
        if (overlap.x <= 0 || overlap.y <= 0) continue
        const axis = overlap.x < overlap.y ? 'x' : 'y'
        const amount = axis === 'x' ? overlap.x : overlap.y
        const before = [items[i].nx, items[i].ny, items[j].nx, items[j].ny]
        pushApart(items[i], items[j], bounds, axis, amount)
        if (before.some((value, index) => value !== [items[i].nx, items[i].ny, items[j].nx, items[j].ny][index])) {
          moved = true
        }
      }
    }
    for (const item of items) clampNudge(item, bounds)
    if (!moved) break
  }

  for (let pass = 0; pass < items.length * 2; pass += 1) {
    let parked = false
    for (let index = 0; index < items.length; index += 1) {
      if (!hitsOther(items[index], items, index, gap) && insideBounds(items[index], bounds)) continue
      if (parkNearAnchor(items[index], items, index, bounds, gap)) parked = true
    }
    if (!parked) break
  }

  return items.map((item) => ({
    x: item.nx,
    y: item.ny,
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
