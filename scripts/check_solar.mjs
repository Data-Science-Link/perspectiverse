import assert from 'node:assert/strict'
import { SITE_TAGLINE, SITE_TITLE, SOLAR_SYSTEM_LABEL, WELCOME_STORAGE_KEY } from '../src/lib/copy.js'
import { solarSettings } from '../src/lib/solarSettings.js'
import { TEXTURE_QUALITY, textureSize } from '../src/lib/planetTextures.js'
import {
  bodyExtent,
  homeLookAt,
  layoutLinear,
  layoutSolarSystem,
  orbitElements,
  orbitRadius,
  orbitsClear,
  systemExtent,
  topicScale,
} from '../src/lib/layout.js'
import {
  clampSolarView,
  clearSolarView,
  mobileOrbitHome,
  orbitSamplePoints,
  projectToCanvas,
  restoreSolarView,
  solarLayoutKey,
  stashSolarView,
} from '../src/lib/solarCamera.js'
import { labelCenterIsClear, ORBIT_LABEL_FONT_PX, orbitLabelCssBox, separateLabelBoxes } from '../src/lib/orbitLabels.js'
import { decorateTopics } from '../src/lib/planets.js'

assert.equal(SITE_TITLE, 'Perspectiverse')
assert.match(SITE_TAGLINE, /perspective/i)
assert.equal(SOLAR_SYSTEM_LABEL, 'Filter topics')
assert.equal(WELCOME_STORAGE_KEY, 'perspectiverse.hide-welcome')

const mobile = solarSettings(true)
const desktop = solarSettings(false)

assert.equal(mobile.bloom, false)
assert.equal(mobile.dreiStars, 0)
assert.ok(mobile.twinkleStars > 0)
assert.equal(mobile.textureQuality, 'low')
assert.equal(mobile.dpr, 1)
assert.equal(mobile.antialias, false)

assert.equal(desktop.bloom, true)
assert.ok(desktop.dreiStars > 0)
assert.ok(desktop.twinkleStars > 0)
assert.equal(desktop.textureQuality, 'high')
assert.deepEqual(desktop.dpr, [1, 1.5])

const [lowW, lowH] = textureSize('low')
const [highW, highH] = textureSize('high')
assert.ok(lowW * lowH < highW * highH)
assert.ok(lowW * lowH <= 256 * 128)
assert.ok(highW * highH <= 512 * 256)
assert.ok(TEXTURE_QUALITY.low.ring < TEXTURE_QUALITY.high.ring)

const volumes = [5.1, 4.6, 3.7, 3.2, 3.1, 2.9, 2.8, 2.5, 2.3, 2.3]
const topics = decorateTopics(volumes.map((total_volume_percent, index) => ({
  id: index + 1,
  total_volume_percent,
})))
const volumeMax = Math.max(...volumes)
const layout = layoutSolarSystem(topics, volumeMax)
assert.equal(layout.radii[0], 0)
assert.ok(orbitsClear(layout), 'equal-rank planets must keep a gap between surfaces')
assert.ok(topicScale(volumeMax, volumeMax) < 1.6)
assert.ok(bodyExtent(2.1, { rings: true }) > bodyExtent(2.1, {}))

const crowded = layoutSolarSystem(
  decorateTopics(Array.from({ length: 10 }, (_, index) => ({ id: index, total_volume_percent: 8 }))),
  8,
)
assert.ok(orbitsClear(crowded), 'same-size planets still get their own lane')

const outer = orbitRadius(9, false)
const extent = systemExtent(10, layout.extent)
assert.ok(extent > layout.radii[9])
assert.ok(layout.radii[9] < 24, `orbits still too wide: ${layout.radii[9]}`)
for (const isMobile of [false, true]) {
  const home = homeLookAt(isMobile, 10, layout.extent)
  const distance = Math.hypot(home[0], home[1], home[2])
  assert.ok(distance > extent, `home camera too close on ${isMobile ? 'mobile' : 'desktop'}: ${distance}`)
  assert.ok(distance < extent * 3.1, `home camera too far on ${isMobile ? 'mobile' : 'desktop'}: ${distance}`)
  assert.ok(home[1] > 3)
  assert.ok(home[2] > outer * 0.4)
}

const tilts = [1, 2, 3, 4, 5, 6, 7, 8, 9].map((index) => orbitElements(index, false, `topic-${index}`).inclination)
assert.ok(Math.max(...tilts) - Math.min(...tilts) > 0.8, 'orbital planes should not all hug the equator')
assert.ok(tilts.some((tilt) => Math.abs(tilt - Math.PI / 2) < 0.65), 'at least one orbit should sit near a right angle')

const line = layoutLinear(topics, volumeMax)
assert.equal(line.mode, 'linear')
assert.equal(line.positions.length, topics.length)
for (let index = 1; index < line.positions.length; index += 1) {
  assert.ok(line.positions[index][0] > line.positions[index - 1][0], 'linear layout runs largest to smallest, left to right')
  assert.equal(line.positions[index][1], 0)
  assert.equal(line.positions[index][2], 0)
}
assert.ok(line.positions[0][0] < 0 && line.positions[line.positions.length - 1][0] > 0, 'the line is centered on the origin')
for (const isMobile of [false, true]) {
  const framed = homeLookAt(isMobile, topics.length, line.extent, { linear: true, extentX: line.extentX, extentY: line.extentY })
  const distance = Math.hypot(framed[0], framed[1], framed[2])
  assert.ok(distance > line.extent * 0.8, `linear camera too close on ${isMobile}`)
}

const gridPortrait = layoutLinear(topics, volumeMax, { grid: true, viewportAspect: 390 / 844 })
assert.equal(gridPortrait.mode, 'grid')
assert.ok(gridPortrait.cols >= 2 && gridPortrait.cols <= 5, `unexpected grid columns: ${gridPortrait.cols}`)
for (let index = 1; index < gridPortrait.positions.length; index += 1) {
  const prev = gridPortrait.positions[index - 1]
  const next = gridPortrait.positions[index]
  const prevRow = Math.floor((index - 1) / gridPortrait.cols)
  const nextRow = Math.floor(index / gridPortrait.cols)
  if (prevRow === nextRow) {
    assert.ok(next[0] > prev[0], 'grid row reads left to right')
    assert.ok(Math.abs(next[1] - prev[1]) < 0.2, 'grid row stays level')
  } else {
    assert.ok(next[1] < prev[1], 'later rows sit below earlier rows')
    assert.ok(next[0] < prev[0], 'each row starts on the left')
  }
}
const gridLandscape = layoutLinear(topics, volumeMax, { grid: true, viewportAspect: 2.54 })
assert.equal(gridLandscape.mode, 'grid')
assert.ok(Math.ceil(topics.length / gridLandscape.cols) <= 2, `landscape should use at most 2 rows: ${gridLandscape.cols} columns`)
assert.ok(gridLandscape.cols >= gridPortrait.cols, 'landscape should not use fewer columns than portrait')
assert.equal(gridPortrait.planetVisualScale, 0.9)
assert.equal(gridLandscape.planetVisualScale, 0.9)

function screenFixture(width, height, aspect) {
  const landscape = aspect > 1.15
  const filterBlock = landscape ? 108 : 124
  return {
    viewport: { width, height },
    usable: { x: 6, y: 8, width: width - 12, height: height - filterBlock - 8 },
  }
}

function assertScreenGrid(aspect, width, height, minDiameter) {
  const placed = layoutLinear(topics, volumeMax, {
    grid: true,
    viewportAspect: aspect,
    screen: screenFixture(width, height, aspect),
  })
  assert.equal(placed.planetVisualScale, 0.9)
  assert.ok(Math.min(...placed.bodyDiameters) >= minDiameter, `diameters ${placed.bodyDiameters}`)
  for (let index = 1; index < placed.bodyDiameters.length; index += 1) {
    assert.ok(placed.bodyDiameters[index] <= placed.bodyDiameters[index - 1] + 1e-6, 'screen diameters stay in size order')
  }
  const places = placed.screenPlaces
  for (let index = 0; index < places.length; index += 1) {
    const place = places[index]
    const radius = placed.bodyDiameters[index] / 2
    const sphere = { x: place.x - radius, y: place.y - radius, width: radius * 2, height: radius * 2 }
    const pill = { x: place.x - 40, y: place.pillTop, width: 80, height: place.pillHeight }
    const overlap = Math.min(sphere.x + sphere.width, pill.x + pill.width) - Math.max(sphere.x, pill.x) > 0
      && Math.min(sphere.y + sphere.height, pill.y + pill.height) - Math.max(sphere.y, pill.y) > 0
    assert.equal(overlap, false, `sphere ${index} meets its pill`)
    assert.ok(place.pillTop >= sphere.y + sphere.height - 1e-6, 'pill starts below the sphere')
  }
}

assertScreenGrid(390 / 844, 390, 844, 28)
assertScreenGrid(2.54, 844, 332, 24)

assert.equal(solarLayoutKey('all', false), 'all:orbit')
assert.equal(solarLayoutKey('World', true, false), 'World:linear')
assert.equal(solarLayoutKey('all', true, true), 'all:grid')
const clamped = clampSolarView(
  { position: [40, 10, 40], target: [30, 0, 0], distance: 50 },
  { minDistance: 3.2, maxDistance: 19.2, extent: 8, linear: false },
)
assert.ok(clamped.distance <= 19.2 + 1e-6)
assert.ok(Math.abs(clamped.target[0]) <= 8 * 0.45 + 1e-6)

function fakeControls(position, target) {
  return {
    getPosition(out) {
      out.set(...position)
      return out
    },
    getTarget(out) {
      out.set(...target)
      return out
    },
    setLookAt(px, py, pz, tx, ty, tz) {
      this.applied = [px, py, pz, tx, ty, tz]
    },
  }
}

const homePose = [0, 4, 12, 0, 0, 0]
const homeLimits = { home: homePose, minDistance: 3.2, maxDistance: 40, extent: 12 }
clearSolarView()
const homeControls = fakeControls([0, 4, 12], [0, 0, 0])
stashSolarView(homeControls, 'all:orbit', homeLimits)
assert.equal(restoreSolarView(homeControls, 'all:orbit', homeLimits, false), false)
assert.equal(homeControls.applied, undefined)
const zoomedControls = fakeControls([0, 4, 8], [0, 0, 0])
stashSolarView(zoomedControls, 'all:orbit', homeLimits)
assert.equal(restoreSolarView(zoomedControls, 'all:orbit', homeLimits, false), true)
assert.deepEqual(zoomedControls.applied, [0, 4, 8, 0, 0, 0])
clearSolarView()

function assertMobileOrbitsFit(frame, chromeInset) {
  const reference = homeLookAt(true, topics.length, layout.extent)
  const referenceDistance = Math.hypot(reference[0], reference[1], reference[2])
  const named = topics.map((topic, index) => ({ ...topic, name: topic.name || `Topic ${index + 1}` }))
  const samples = orbitSamplePoints(named, layout)
  const fitted = mobileOrbitHome(layout.extent, frame, { samples, referenceDistance, baseDistanceFactor: 16 })
  assert.equal(fitted.labelDistanceFactor, 16)
  assert.ok(fitted.distance < referenceDistance * 1.35, `phone camera backed too far: ${fitted.distance} vs ${referenceDistance}`)
  assert.ok(fitted.distance > referenceDistance * 0.45, `phone camera too close: ${fitted.distance}`)
  assert.ok(ORBIT_LABEL_FONT_PX >= 10)
  const chromeTop = frame.height - chromeInset
  const boxW = frame.usable.width
  const boxH = frame.usable.height
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const sample of samples) {
    const css = orbitLabelCssBox(sample.name, frame.width)
    const label = projectToCanvas(sample.label, fitted.lookAt, frame.width, frame.height)
    const planet = projectToCanvas(sample.planet, fitted.lookAt, frame.width, frame.height)
    assert.equal(label.behind, false, `${sample.name} label sits behind the phone camera`)
    assert.equal(planet.behind, false, `${sample.name} sits behind the phone camera`)
    const left = label.x - css.width / 2
    const right = label.x + css.width / 2
    const top = label.y - css.height / 2
    const bottom = label.y + css.height / 2
    assert.ok(left >= 2 && right <= frame.width - 2, `${sample.name} label x ${left}..${right}`)
    assert.ok(top >= 2 && bottom <= chromeTop - 2, `${sample.name} label y ${top}..${bottom} chrome ${chromeTop}`)
    minX = Math.min(minX, left, planet.x)
    maxX = Math.max(maxX, right, planet.x)
    minY = Math.min(minY, top, planet.y)
    maxY = Math.max(maxY, bottom, planet.y)
  }
  const fill = Math.max((maxX - minX) / boxW, (maxY - minY) / boxH)
  assert.ok(fill > 0.62, `cluster should fill the usable area, fill ${fill}`)
}

assertMobileOrbitsFit(
  { width: 390, height: 776, usable: { x: 8, y: 8, width: 374, height: 776 - 119 - 8 } },
  119,
)
assertMobileOrbitsFit(
  { width: 844, height: 332, usable: { x: 8, y: 8, width: 828, height: 332 - 119 - 8 } },
  119,
)

function boxesIntersect(a, b) {
  const overlapX = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)
  const overlapY = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)
  return overlapX > 0 && overlapY > 0
}

function placeNudged(boxes, nudges) {
  return boxes.map((box, index) => ({
    x: Math.round(box.x) + nudges[index].x,
    y: Math.round(box.y) + nudges[index].y,
    w: Math.round(box.w),
    h: Math.round(box.h),
  }))
}

function assertSeparated(boxes, area, label) {
  const nudges = separateLabelBoxes(boxes, area)
  const placed = placeNudged(boxes, nudges)
  assert.equal(labelCenterIsClear(placed), true, label)
  assert.deepEqual(separateLabelBoxes(boxes, area), nudges, `${label} stable`)
  for (let i = 0; i < placed.length; i += 1) {
    const box = placed[i]
    assert.ok(box.x >= area.left && box.y >= area.top, label)
    assert.ok(box.x + box.w <= area.right && box.y + box.h <= area.bottom, label)
    for (let j = i + 1; j < placed.length; j += 1) {
      assert.equal(boxesIntersect(box, placed[j]), false, `${label} ${i} overlaps ${j}`)
    }
  }
}

const bounds = { left: 0, top: 0, right: 400, bottom: 400 }
assertSeparated([
  { x: 100, y: 100, w: 60, h: 12 },
  { x: 110, y: 102, w: 50, h: 12 },
], bounds, 'stacked')
assertSeparated([
  { x: 40.4, y: 300.2, w: 111, h: 19 },
  { x: 41.1, y: 301.4, w: 110, h: 19 },
], { left: 4, top: 4, right: 386, bottom: 640 }, 'coincident pills')
assertSeparated(
  Array.from({ length: 10 }, () => ({ x: 180, y: 360, w: 100, h: 19 })),
  { left: 4, top: 8, right: 386, bottom: 640 },
  'ten labels on one spot',
)

const desktopHome = homeLookAt(false, 10, layout.extent)
assert.equal(desktopHome.length, 6)
assert.equal(desktopHome[3], 0)
assert.equal(desktopHome[4], 0)
assert.equal(desktopHome[5], 0)

console.log('solar system settings, tagline, and texture quality ok')
