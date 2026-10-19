export const PLANET_MESH_RADIUS = 0.95
export const SUN_HALO_RADIUS = 1.28
export const SATURN_RING_RADIUS = 1.72
export const ORBIT_CLEARANCE = 0.34
const LABEL_PAD = 1.35
export const GRID_PLANET_SCALE = 0.9
export const GRID_LABEL_GAP = 0.38
const GRID_ROW_GAP = 0.5

export function topicScale(volumePercent, systemMaxPercent = 100) {
  const relative = Math.max(0, Number(volumePercent) || 0) / Math.max(Number(systemMaxPercent) || 0, 0.01)
  return 0.38 + Math.min(relative, 1) * 1.05
}

export function bodyExtent(scale, { sun = false, rings = false } = {}) {
  let radius = Math.max(0, Number(scale) || 0) * PLANET_MESH_RADIUS
  if (sun) radius = Math.max(radius, scale * SUN_HALO_RADIUS)
  if (rings) radius = Math.max(radius, scale * SATURN_RING_RADIUS)
  return radius
}

function fallbackOrbitRadius(index) {
  return 3.1 + index * 1.85
}

export function orbitRadius(index, isSun) {
  if (isSun) return 0
  return fallbackOrbitRadius(index)
}

export function layoutSolarSystem(topics = [], volumeMax = 100) {
  const items = topics.map((topic, index) => {
    const scale = topicScale(topic.total_volume_percent, volumeMax)
    const sun = index === 0 || topic.body?.key === 'sun'
    const rings = Boolean(topic.body?.rings)
    return {
      scale,
      extent: bodyExtent(scale, { sun, rings }),
      sun,
      rings,
    }
  })

  const radii = []
  let lane = 0
  for (let i = 0; i < items.length; i += 1) {
    if (i === 0) {
      radii.push(0)
      lane = items[i].extent + ORBIT_CLEARANCE
      continue
    }
    const radius = lane + items[i].extent
    radii.push(radius)
    lane = radius + items[i].extent + ORBIT_CLEARANCE
  }

  const outerIndex = Math.max(items.length - 1, 0)
  const outerRadius = radii[outerIndex] ?? 0
  const outerExtent = items[outerIndex]?.extent ?? 0
  return {
    items,
    radii,
    extent: outerRadius + outerExtent + LABEL_PAD,
  }
}

function linearRowSpecs(topics, volumeMax, { visualScale = 1 } = {}) {
  const shrink = Math.max(0.55, Math.min(1, Number(visualScale) || 1))
  return topics.map((topic, index) => {
    const scale = topicScale(topic.total_volume_percent, volumeMax) * shrink
    const sun = index === 0 || topic.body?.key === 'sun'
    const rings = Boolean(topic.body?.rings)
    return { extent: bodyExtent(scale, { sun, rings }), scale }
  })
}

function labelFootprintUnits(name, extent, gap, viewportAspect = 1) {
  const text = String(name ?? '')
  const chars = Math.max(4, text.length)
  const portrait = viewportAspect < 0.9
  const landscape = viewportAspect > 1.15
  const charsPerLine = portrait ? 15 : landscape ? 16 : 20
  const lines = Math.ceil(chars / charsPerLine)
  const lineWidth = portrait ? 5.4 : landscape ? 8.6 : 6.2
  const wrappedWidth = lineWidth * Math.min(lines, 2)
  return Math.max(extent * 2 + gap + 0.6, wrappedWidth)
}

function labelLineCount(name, viewportAspect = 1) {
  const text = String(name ?? '')
  const chars = Math.max(4, text.length)
  const portrait = viewportAspect < 0.9
  const landscape = viewportAspect > 1.15
  const charsPerLine = portrait ? 14 : landscape ? 16 : 20
  return Math.min(3, Math.ceil(chars / charsPerLine))
}

function labelBandUnits(lines, viewportAspect = 1) {
  const portrait = viewportAspect < 0.9
  const landscape = viewportAspect > 1.15
  if (portrait) return 1.05 + lines * 1.38
  if (landscape) return 1.55 + lines * 1.92
  return 2.4
}

function gridRowHeight(extent, name, viewportAspect) {
  const lines = labelLineCount(name, viewportAspect)
  const labelBand = labelBandUnits(lines, viewportAspect)
  const landscape = viewportAspect > 1.15
  const rowGap = landscape ? 1.05 : GRID_ROW_GAP
  return extent * 2 + GRID_LABEL_GAP + labelBand + rowGap
}

function gridColWidth(extent, name, viewportAspect) {
  const textWidth = labelFootprintUnits(name, extent, GRID_ROW_GAP, viewportAspect)
  return Math.max(extent * 2 + GRID_ROW_GAP, textWidth)
}

function gridExtentsForColumnCount(n, cols, specs, topics, viewportAspect) {
  const rows = Math.ceil(n / cols)
  const colWidths = Array.from({ length: cols }, () => 0)
  const rowHeights = Array.from({ length: rows }, () => 0)
  const maxExtentPerRow = Array.from({ length: rows }, () => 0)
  for (let index = 0; index < n; index += 1) {
    const row = Math.floor(index / cols)
    const col = index % cols
    const extent = specs[index].extent
    const name = topics[index]?.name ?? ''
    colWidths[col] = Math.max(colWidths[col], gridColWidth(extent, name, viewportAspect))
    rowHeights[row] = Math.max(rowHeights[row], gridRowHeight(extent, name, viewportAspect))
    maxExtentPerRow[row] = Math.max(maxExtentPerRow[row], extent)
  }
  const totalWidth = colWidths.reduce((sum, value) => sum + value, 0)
  const totalHeight = rowHeights.reduce((sum, value) => sum + value, 0)
  const labelPad = LABEL_PAD * 1.15
  let minBound = Infinity
  let maxBound = -Infinity
  for (let index = 0; index < n; index += 1) {
    const row = Math.floor(index / cols)
    const rowTop = totalHeight / 2 - rowHeights.slice(0, row).reduce((sum, h) => sum + h, 0)
    const y = rowTop - specs[index].extent
    const extent = specs[index].extent
    const name = topics[index]?.name ?? ''
    const lines = labelLineCount(name, viewportAspect)
    const labelBand = labelBandUnits(lines, viewportAspect)
    maxBound = Math.max(maxBound, y + extent)
    minBound = Math.min(minBound, y - extent - GRID_LABEL_GAP - labelBand)
  }
  if (viewportAspect > 1.15) minBound -= 0.18
  const extentX = totalWidth / 2 + labelPad
  const contentExtentY = (maxBound - minBound) / 2 + labelPad
  return { rows, totalWidth, totalHeight, extentX, contentExtentY }
}

function landscapePhoneGridFits(extentX, extentY, aspect, rows, count, cols, options = {}) {
  if (rows === 1 && count >= 8) return false
  const fovRad = (48 * Math.PI) / 360
  const horizontalHalf = Math.atan(Math.tan(fovRad) * aspect)
  const verticalHalf = fovRad
  const margin = 1.1
  const filterFrac = 0.32
  const distanceH = (extentX / Math.tan(horizontalHalf)) * margin
  const distanceV = (extentY / Math.tan(verticalHalf)) * margin
  const distance = Math.max(distanceH, distanceV)
  const visibleHeight = 2 * distance * Math.tan(verticalHalf)
  const usableHeight = visibleHeight * (1 - filterFrac)
  if (extentY * 2 > usableHeight * 0.88) return false
  if (options.skipColPixels) return true
  const visibleWidth = 2 * distance * Math.tan(horizontalHalf)
  const colWorld = (2 * extentX) / cols
  const viewportWidth = aspect * 390
  const colPixels = (colWorld / visibleWidth) * viewportWidth
  const minColPixels = 165 * (aspect / 2.54)
  return colPixels >= minColPixels
}

function stretchGridVertically(rowStarts, positions, cols, viewportAspect, rowHeights) {
  if (rowStarts.length <= 1) return
  const portrait = viewportAspect < 0.9
  if (!portrait) return
  const minY = Math.min(...rowStarts)
  const maxY = Math.max(...rowStarts)
  const span = maxY - minY
  if (span < 1e-6) return
  const targetSpan = rowHeights.reduce((sum, h) => sum + h, 0) * 1.04
  const scale = Math.max(1, targetSpan / span)
  const mid = (maxY + minY) / 2
  for (let row = 0; row < rowStarts.length; row += 1) {
    rowStarts[row] = mid + (rowStarts[row] - mid) * scale
  }
  for (let index = 0; index < positions.length; index += 1) {
    const row = Math.floor(index / cols)
    positions[index][1] = rowStarts[row]
  }
}

export function pickLinearGridColumns(count, viewportAspect = 1, specs = [], topics = [], { maxColumns = 2 } = {}) {
  const n = Math.max(0, Number(count) || 0)
  if (n <= 1) return 1
  const landscape = viewportAspect > 1.15
  const maxCols = Math.min(n, Math.max(1, Number(maxColumns) || 2))
  if (landscape) {
    const aspect = Math.max(0.35, Math.min(3.2, viewportAspect))
    for (let targetRows = 1; targetRows <= n; targetRows += 1) {
      let bestCols = 0
      for (let cols = Math.ceil(n / targetRows); cols <= maxCols; cols += 1) {
        if (Math.ceil(n / cols) !== targetRows) continue
        const { rows, extentX, contentExtentY } = gridExtentsForColumnCount(n, cols, specs, topics, viewportAspect)
        if (!landscapePhoneGridFits(extentX, contentExtentY, aspect, rows, n, cols)) continue
        bestCols = Math.max(bestCols, cols)
      }
      if (bestCols > 0) return bestCols
    }
    return Math.max(Math.ceil(n / 2), 1)
  }
  const aspect = Math.max(0.35, Math.min(3.2, Number(viewportAspect) || 1))
  let bestCols = 1
  let bestScore = Infinity
  for (let cols = 1; cols <= Math.min(n, maxCols); cols += 1) {
    const rows = Math.ceil(n / cols)
    const colWidths = Array.from({ length: cols }, () => 0)
    const rowHeights = Array.from({ length: rows }, () => 0)
    for (let index = 0; index < n; index += 1) {
      const row = Math.floor(index / cols)
      const col = index % cols
      const extent = specs[index]?.extent ?? 0.8
      const name = topics[index]?.name ?? ''
      const span = gridColWidth(extent, name, viewportAspect)
      colWidths[col] = Math.max(colWidths[col], span)
      rowHeights[row] = Math.max(rowHeights[row], gridRowHeight(extent, name, viewportAspect))
    }
    const width = colWidths.reduce((sum, value) => sum + value, 0)
    const height = rowHeights.reduce((sum, value) => sum + value, 0)
    const score = Math.max(width / aspect, height)
    if (score < bestScore - 1e-6 || (Math.abs(score - bestScore) <= 1e-6 && cols < bestCols)) {
      bestScore = score
      bestCols = cols
    }
  }
  return bestCols
}

function layoutLinearGrid(specs, viewportAspect = 1, topics = []) {
  const n = specs.length
  if (n === 0) {
    return { positions: [], extent: LABEL_PAD, extentY: LABEL_PAD, mode: 'grid', cols: 1 }
  }
  const landscape = viewportAspect > 1.15
  const maxColumns = landscape ? n : 2
  const cols = pickLinearGridColumns(n, viewportAspect, specs, topics, { maxColumns })
  const rows = Math.ceil(n / cols)
  const colWidths = Array.from({ length: cols }, () => 0)
  const rowHeights = Array.from({ length: rows }, () => 0)
  const maxExtentPerRow = Array.from({ length: rows }, () => 0)
  for (let index = 0; index < n; index += 1) {
    const row = Math.floor(index / cols)
    const col = index % cols
    const extent = specs[index].extent
    const name = topics[index]?.name ?? ''
    colWidths[col] = Math.max(colWidths[col], gridColWidth(extent, name, viewportAspect))
    rowHeights[row] = Math.max(rowHeights[row], gridRowHeight(extent, name, viewportAspect))
    maxExtentPerRow[row] = Math.max(maxExtentPerRow[row], extent)
  }
  const totalWidth = colWidths.reduce((sum, value) => sum + value, 0)
  const totalHeight = rowHeights.reduce((sum, value) => sum + value, 0)
  const colStarts = []
  let xCursor = -totalWidth / 2
  for (const width of colWidths) {
    colStarts.push(xCursor + width / 2)
    xCursor += width
  }
  function yTopForRow(row, heights, totalH) {
    let top = totalH / 2
    for (let r = 0; r < row; r += 1) top -= heights[r]
    return top
  }

  const rowSphereY = []
  for (let row = 0; row < rows; row += 1) {
    const rowTop = yTopForRow(row, rowHeights, totalHeight)
    rowSphereY.push(rowTop - maxExtentPerRow[row])
  }

  const positions = specs.map((_, index) => {
    const row = Math.floor(index / cols)
    const col = index % cols
    return [colStarts[col], rowSphereY[row], 0]
  })

  stretchGridVertically(rowSphereY, positions, cols, viewportAspect, rowHeights)

  if (landscape) {
    const yShift = 1.05
    const rowSpread = 3.78
    for (let index = 0; index < positions.length; index += 1) {
      const row = Math.floor(index / cols)
      positions[index][1] += yShift - row * rowSpread
    }
  }

  const labelPad = LABEL_PAD * 1.15
  let minBound = Infinity
  let maxBound = -Infinity
  for (let index = 0; index < n; index += 1) {
    const y = positions[index][1]
    const extent = specs[index].extent
    const name = topics[index]?.name ?? ''
    const lines = labelLineCount(name, viewportAspect)
    const labelBand = labelBandUnits(lines, viewportAspect)
    maxBound = Math.max(maxBound, y + extent)
    minBound = Math.min(minBound, y - extent - GRID_LABEL_GAP - labelBand)
  }
  if (viewportAspect < 0.9) minBound -= 0.45
  if (landscape) minBound -= 0.18
  const extentX = totalWidth / 2 + labelPad
  const contentExtentY = (maxBound - minBound) / 2 + labelPad
  const extentY = contentExtentY
  return {
    positions,
    extent: Math.max(extentX, extentY),
    extentX,
    extentY,
    mode: 'grid',
    cols,
    rows,
  }
}

function layoutLinearRow(specs) {
  const gap = 1.7
  let cursor = 0
  const centers = []
  for (const spec of specs) {
    centers.push(cursor + spec.extent)
    cursor += spec.extent * 2 + gap
  }
  const width = Math.max(cursor - gap, 0)
  const shift = width / 2
  const positions = centers.map((center) => [center - shift, 0, 0])
  const extent = width / 2 + LABEL_PAD
  return {
    positions,
    extent,
    extentX: extent,
    extentY: LABEL_PAD,
    mode: 'linear',
    cols: specs.length,
  }
}

export const GRID_MIN_DIAMETER = { portrait: 28, landscape: 24 }
const GRID_FOV_DEG = 48
const GRID_PX_PER_WORLD = 12
const GRID_PILL_GAP_PX = 8
const GRID_ROW_GAP_PX = 8

export function gridMinDiameter(viewportAspect = 1) {
  return viewportAspect > 1.15 ? GRID_MIN_DIAMETER.landscape : GRID_MIN_DIAMETER.portrait
}

export function splitLabelLines(name) {
  const text = String(name ?? '').trim()
  if (!text) return ['']
  const spaces = []
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === ' ') spaces.push(index)
  }
  if (spaces.length === 0) return [text]
  let best = spaces[0]
  let bestScore = Infinity
  for (const index of spaces) {
    const score = Math.max(index, text.length - index - 1)
    if (score < bestScore) {
      bestScore = score
      best = index
    }
  }
  return [text.slice(0, best), text.slice(best + 1)]
}

function bodyRadiusFactor(topic, index) {
  const sun = index === 0 || topic?.body?.key === 'sun'
  return sun ? SUN_HALO_RADIUS : PLANET_MESH_RADIUS
}

function visualRadiusFactor(topic, index) {
  if (topic?.body?.rings) return SATURN_RING_RADIUS
  return bodyRadiusFactor(topic, index)
}

export function screenDiametersFromRadii(radii, minPx, maxPx) {
  const floor = Math.max(1, Math.min(minPx, maxPx))
  const cap = Math.max(floor, maxPx)
  const lo = Math.min(...radii)
  const hi = Math.max(...radii)
  const raw = radii.map((radius) => {
    if (!(hi > lo)) return cap
    const t = (radius - lo) / (hi - lo)
    return floor + t * (cap - floor)
  })
  const diameters = []
  for (let index = 0; index < raw.length; index += 1) {
    let value = Math.min(cap, Math.max(floor, raw[index]))
    if (index > 0) value = Math.min(value, diameters[index - 1])
    diameters.push(value)
  }
  return diameters
}

function packPhoneRows({ count, cols, visualDiameters, pillHeights, usable, gapPx, rowGapPx }) {
  const rows = Math.max(1, Math.ceil(count / cols))
  const rowSphere = Array.from({ length: rows }, () => 0)
  const rowPill = Array.from({ length: rows }, () => 0)
  for (let index = 0; index < count; index += 1) {
    const row = Math.floor(index / cols)
    rowSphere[row] = Math.max(rowSphere[row], visualDiameters[index] || 0)
    rowPill[row] = Math.max(rowPill[row], pillHeights[index] || 0)
  }
  const cells = rowSphere.map((sphere, row) => sphere + gapPx + rowPill[row])
  const base = cells.reduce((sum, value) => sum + value, 0) + rowGapPx * Math.max(0, rows - 1)
  const extra = usable.height - base
  const edgePad = rows === 1 ? Math.max(0, extra / 2) : Math.max(0, Math.min(10, extra * 0.08))
  const rowGap = rowGapPx + (rows > 1 ? Math.max(0, (extra - edgePad * 2) / (rows - 1)) : 0)
  const places = []
  const colWidth = usable.width / cols
  let cursor = usable.y + edgePad
  for (let row = 0; row < rows; row += 1) {
    const band = rowSphere[row]
    const centerY = cursor + band / 2
    const pillTop = cursor + band + gapPx
    for (let col = 0; col < cols; col += 1) {
      const index = row * cols + col
      if (index >= count) break
      places.push({
        index,
        row,
        col,
        x: usable.x + colWidth * (col + 0.5),
        y: centerY,
        diameter: visualDiameters[index],
        pillTop,
        colWidth,
      })
    }
    cursor += band + gapPx + rowPill[row] + (row < rows - 1 ? rowGap : 0)
  }
  return {
    places,
    colWidth,
    contentBottom: cursor,
    overflow: cursor - (usable.y + usable.height),
  }
}

function estimatePillHeight(name, maxWidth, { landscape = false, fontSize = 18 } = {}) {
  const text = String(name ?? '')
  const padX = 16
  const padY = 8
  const charPx = fontSize * (landscape ? 0.58 : 0.56)
  if (landscape) {
    const lines = splitLabelLines(text)
    const lineWidth = Math.max(...lines.map((line) => line.length * charPx))
    return {
      width: Math.min(maxWidth, lineWidth + padX),
      height: lines.length * fontSize * 1.2 + padY,
    }
  }
  const inner = Math.max(24, maxWidth - padX)
  const perLine = Math.max(4, Math.floor(inner / charPx))
  const lines = Math.max(1, Math.ceil(Math.max(1, text.length) / perLine))
  return {
    width: maxWidth,
    height: lines * fontSize * 1.46 + padY,
  }
}

export function placePhoneGrid({
  topics = [],
  volumeMax = 100,
  cols = 2,
  usable,
  viewport,
  pills = null,
  viewportAspect = 1,
}) {
  const count = topics.length
  const landscape = viewportAspect > 1.15
  const minPx = gridMinDiameter(viewportAspect)
  const rows = Math.max(1, Math.ceil(count / Math.max(cols, 1)))
  const colWidth = usable.width / Math.max(cols, 1)
  const hardCap = Math.max(
    minPx,
    Math.min(colWidth * 0.8, Math.max(minPx, (usable.height / rows) * 0.7), 96),
  )
  const pillMaxWidth = Math.max(72, colWidth - 8)
  const fontSize = landscape ? 14 : 18
  const pillHeights = []
  const radii = []
  const bodyFactors = []
  const visualFactors = []
  for (let index = 0; index < count; index += 1) {
    const topic = topics[index]
    const measured = pills?.[index]
    const estimated = estimatePillHeight(topic?.name, pillMaxWidth, { landscape, fontSize })
    pillHeights.push(Math.max(18, measured?.height || estimated.height))
    const natural = topicScale(topic?.total_volume_percent, volumeMax)
    const bodyFactor = bodyRadiusFactor(topic, index)
    bodyFactors.push(bodyFactor)
    visualFactors.push(visualRadiusFactor(topic, index))
    radii.push(natural * bodyFactor)
  }

  function solve(floor, gapPx, rowGapPx) {
    let lo = floor
    let hi = Math.max(floor, hardCap)
    let best = null
    for (let step = 0; step < 16; step += 1) {
      const mid = step === 0 ? hi : (lo + hi) / 2
      const bodyD = screenDiametersFromRadii(radii, floor, mid)
      const visualD = bodyD.map((diameter, index) => diameter * (visualFactors[index] / bodyFactors[index]))
      const packed = packPhoneRows({
        count,
        cols,
        visualDiameters: visualD,
        pillHeights,
        usable,
        gapPx,
        rowGapPx,
      })
      const fits = packed.overflow <= 0.5
      if (fits) {
        best = { bodyD, visualD, packed }
        lo = mid
      } else {
        hi = mid
      }
    }
    return best
  }

  let placed = null
  const gapOptions = [
    [GRID_PILL_GAP_PX, GRID_ROW_GAP_PX],
    [6, 6],
    [4, 4],
  ]
  const floors = [minPx + 4, minPx]
  for (const floor of floors) {
    if (placed) break
    for (const [gapPx, rowGapPx] of gapOptions) {
      const solved = solve(floor, gapPx, rowGapPx)
      if (solved && Math.min(...solved.bodyD) >= minPx - 0.01) {
        placed = solved
        break
      }
    }
  }
  if (!placed) {
    const bodyD = screenDiametersFromRadii(radii, minPx, minPx)
    const visualD = bodyD.map((diameter, index) => diameter * (visualFactors[index] / bodyFactors[index]))
    placed = {
      bodyD,
      visualD,
      packed: packPhoneRows({
        count,
        cols,
        visualDiameters: visualD,
        pillHeights,
        usable,
        gapPx: 4,
        rowGapPx: 4,
      }),
    }
  }

  const px = GRID_PX_PER_WORLD
  const width = viewport.width
  const height = viewport.height
  const halfFov = (GRID_FOV_DEG * Math.PI) / 360
  const distance = height / (px * 2 * Math.tan(halfFov))
  const positions = placed.packed.places.map((place) => ([
    (place.x - width / 2) / px,
    (height / 2 - place.y) / px,
    0,
  ]))
  const meshScales = placed.bodyD.map((diameter, index) => (diameter / 2) / px / bodyFactors[index])
  const screenPlaces = placed.packed.places.map((place, index) => ({
    ...place,
    bodyDiameter: placed.bodyD[index],
    pillHeight: pillHeights[index],
  }))
  let maxAbsX = 1
  let maxAbsY = 1
  for (const position of positions) {
    maxAbsX = Math.max(maxAbsX, Math.abs(position[0]))
    maxAbsY = Math.max(maxAbsY, Math.abs(position[1]))
  }
  return {
    positions,
    meshScales,
    screenPlaces,
    camera: [0, 0, distance, 0, 0, 0],
    pillMaxWidth,
    bodyDiameters: placed.bodyD,
    extentX: maxAbsX + 1,
    extentY: maxAbsY + 1,
    extent: Math.max(maxAbsX, maxAbsY) + 1,
  }
}

export function layoutLinear(topics = [], volumeMax = 100, options = {}) {
  const grid = Boolean(options.grid)
  const aspect = options.viewportAspect ?? 1
  const visualScale = grid ? GRID_PLANET_SCALE : 1
  const specs = linearRowSpecs(topics, volumeMax, { visualScale })
  if (grid && specs.length > 0) {
    const gridLayout = layoutLinearGrid(specs, aspect, topics)
    const screen = options.screen
    if (screen?.usable && screen?.viewport && topics.length > 0) {
      const placed = placePhoneGrid({
        topics,
        volumeMax,
        cols: gridLayout.cols,
        usable: screen.usable,
        viewport: screen.viewport,
        pills: screen.pills,
        viewportAspect: aspect,
      })
      return {
        ...gridLayout,
        ...placed,
        mode: 'grid',
        cols: gridLayout.cols,
        rows: gridLayout.rows,
        planetVisualScale: GRID_PLANET_SCALE,
      }
    }
    return { ...gridLayout, planetVisualScale: visualScale }
  }
  return { ...layoutLinearRow(specs), planetVisualScale: 1 }
}

export function orbitsClear(layout) {
  const { items = [], radii = [] } = layout ?? {}
  for (let i = 0; i < items.length; i += 1) {
    for (let j = i + 1; j < items.length; j += 1) {
      const gap = Math.abs((radii[j] ?? 0) - (radii[i] ?? 0)) - items[i].extent - items[j].extent
      if (gap < ORBIT_CLEARANCE - 1e-6) return false
    }
  }
  return true
}

export function systemExtent(planetCount = 10, layoutExtent = null) {
  if (layoutExtent != null) return layoutExtent
  const outerIndex = Math.max(1, Number(planetCount) - 1)
  return orbitRadius(outerIndex, false) + SUN_HALO_RADIUS * 2.3 + LABEL_PAD
}

export function homeLookAt(isMobile = false, planetCount = 10, layoutExtent = null, options = {}) {
  if (Array.isArray(options.camera) && options.camera.length >= 6) {
    return options.camera.slice(0, 6)
  }
  const extent = systemExtent(planetCount, layoutExtent)
  const fov = isMobile ? 48 : 42
  const half = (fov * Math.PI) / 360
  if (options.linear) {
    const aspect = options.viewportAspect ?? (isMobile ? 0.58 : 1.2)
    const horizontalHalf = Math.atan(Math.tan(half) * aspect)
    const verticalHalf = half
    const extentX = options.extentX ?? extent
    const portrait = aspect < 0.9
    const landscape = aspect > 1.15
    const extentY = options.extentY ?? extent
    const distanceH = extentX / Math.tan(horizontalHalf)
    const distanceV = extentY / Math.tan(verticalHalf)
    const mobileMargin = options.grid ? (portrait ? 1.04 : landscape ? 1.2 : 1.06) : 1.12
    const distance = Math.max(distanceH, distanceV) * (isMobile ? mobileMargin : 1.06)
    const yLift = options.grid ? (portrait ? 0.1 : landscape ? 0.22 : 0.14) : 0.22
    const y = distance * yLift
    const z = Math.sqrt(Math.max(distance * distance - y * y, 1))
    const targetY = options.grid && landscape && isMobile ? -7.2 : 0
    return [0, y, z, 0, targetY, 0]
  }
  const distance = (extent / Math.sin(half)) * (isMobile ? 1.04 : 1.0)
  const y = distance * (isMobile ? 0.26 : 0.32)
  const z = Math.sqrt(Math.max(distance * distance - y * y, 1))
  return [0, y, z, 0, 0, 0]
}

export function homeMaxDistance(isMobile = false, planetCount = 10, layoutExtent = null, options = {}) {
  const [x, y, z] = homeLookAt(isMobile, planetCount, layoutExtent, options)
  return Math.hypot(x, y, z) * 1.35
}

function unitHash(seed) {
  const n = Math.sin(seed * 127.1 + 311.7) * 43758.5453123
  return n - Math.floor(n)
}

function seedFrom(id, index) {
  const text = String(id ?? index)
  let hash = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0) + index * 97
}

function randomUnit(seedA, seedB) {
  const z = unitHash(seedA) * 2 - 1
  const theta = unitHash(seedB) * Math.PI * 2
  const radial = Math.sqrt(Math.max(1 - z * z, 0))
  return [radial * Math.cos(theta), z, radial * Math.sin(theta)]
}

export function orbitElements(index, isSun, id, radius = null) {
  if (isSun) {
    return { radius: 0, speed: 0, inclination: 0, node: 0, phase: 0 }
  }

  const seed = seedFrom(id, index)
  const kepler = 0.105 / Math.sqrt(index + 1.55)
  const speedScale = 0.58 + unitHash(seed + 11) * 1.05
  const direction = unitHash(seed + 23) >= 0.5 ? 1 : -1
  // Uniform random orbital plane: some sit near the equator, some near a right angle.
  const inclination = Math.acos(Math.min(1, Math.max(-1, 2 * unitHash(seed + 41) - 1)))
  const node = unitHash(seed + 53) * Math.PI * 2
  // Full-range random starting angle so planets are evenly distributed on first load.
  const phase = unitHash(seed + 67) * Math.PI * 2

  return {
    radius: radius ?? orbitRadius(index, false),
    speed: kepler * speedScale * direction,
    inclination,
    node,
    phase,
  }
}

// Module-level clock so planet orbital angles survive Observatory remounts (e.g. mobile
// navigate-to-reading → back). Keyed by topic id; cleared lazily via normal GC since topic
// sets are small and stable within a session.
const _orbitClock = new Map()

export function resumeOrbitAngle(id, initial) {
  return _orbitClock.has(id) ? _orbitClock.get(id) : initial
}

export function saveOrbitAngle(id, angle) {
  _orbitClock.set(id, angle)
}

export function bodySpin(id, index = 0) {
  const seed = seedFrom(id, index)
  const speed = 0.28 + unitHash(seed + 97) * 0.22
  return {
    axis: randomUnit(seed + 71, seed + 83),
    speed,
  }
}

export function setOrbitPosition(target, radius, angle, inclination, node) {
  const cosT = Math.cos(angle)
  const sinT = Math.sin(angle)
  const cosO = Math.cos(node)
  const sinO = Math.sin(node)
  const cosI = Math.cos(inclination)
  const sinI = Math.sin(inclination)
  target.set(
    radius * (cosO * cosT - sinO * sinT * cosI),
    radius * (sinT * sinI),
    radius * (sinO * cosT + cosO * sinT * cosI),
  )
  return target
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

export function allocatePercents(weights = [], decimals = 1) {
  const count = weights.length
  if (count === 0) return []
  const scale = 10 ** decimals
  const target = 100 * scale
  const numeric = weights.map((value) => Math.max(0, Number(value) || 0))
  const total = numeric.reduce((sum, value) => sum + value, 0)
  if (total <= 0) {
    const even = Math.floor(target / count)
    const parts = Array.from({ length: count }, () => even)
    let leftover = target - even * count
    for (let index = 0; leftover > 0; index += 1, leftover -= 1) {
      parts[index % count] += 1
    }
    return parts.map((value) => value / scale)
  }

  const raw = numeric.map((value) => (value / total) * target)
  const floors = raw.map((value) => Math.floor(value + 1e-9))
  let remainder = target - floors.reduce((sum, value) => sum + value, 0)
  const order = raw
    .map((value, index) => ({ index, frac: value - floors[index] }))
    .sort((a, b) => b.frac - a.frac || a.index - b.index)
  const parts = floors.slice()
  for (let index = 0; index < remainder; index += 1) {
    parts[order[index % count].index] += 1
  }
  return parts.map((value) => value / scale)
}

export function withSharePercents(topics = []) {
  const shares = allocatePercents(topics.map((topic) => topic.total_volume_percent))
  return topics.map((topic, index) => {
    const perspectives = topic.perspectives ?? []
    const faceShares = perspectives.length
      ? allocatePercents(perspectives.map((face) => face.volume_percent))
      : []
    return {
      ...topic,
      total_volume_percent: shares[index],
      perspectives: perspectives.map((face, faceIndex) => ({
        ...face,
        volume_percent: faceShares[faceIndex],
      })),
    }
  })
}

export function sortPosts(posts = []) {
  return [...posts].sort((a, b) => {
    const aMatch = a.match == null ? null : Number(a.match)
    const bMatch = b.match == null ? null : Number(b.match)
    if (aMatch != null || bMatch != null) {
      const delta = (bMatch ?? -1) - (aMatch ?? -1)
      if (delta !== 0) return delta
    }
    return (b.likes ?? 0) - (a.likes ?? 0)
  })
}
