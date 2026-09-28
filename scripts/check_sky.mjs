import assert from 'node:assert/strict'
import { SITE_TAGLINE, SITE_TITLE, SOLAR_SYSTEM_LABEL, WELCOME_STORAGE_KEY } from '../src/lib/copy.js'
import { skySettings } from '../src/lib/skySettings.js'
import { TEXTURE_QUALITY, textureSize } from '../src/lib/planetTextures.js'
import {
  bodyExtent,
  homeLookAt,
  layoutSky,
  orbitRadius,
  orbitsClear,
  systemExtent,
  topicScale,
} from '../src/lib/layout.js'
import { decorateTopics } from '../src/lib/planets.js'

assert.equal(SITE_TITLE, 'Perspectiverse')
assert.match(SITE_TAGLINE, /perspective/i)
assert.equal(SOLAR_SYSTEM_LABEL, 'Filter topics')
assert.equal(WELCOME_STORAGE_KEY, 'perspectiverse.hide-welcome')

const mobile = skySettings(true)
const desktop = skySettings(false)

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
const layout = layoutSky(topics, volumeMax)
assert.equal(layout.radii[0], 0)
assert.ok(orbitsClear(layout), 'equal-rank planets must keep a gap between surfaces')
assert.ok(topicScale(volumeMax, volumeMax) < 2.4)
assert.ok(bodyExtent(2.1, { rings: true }) > bodyExtent(2.1, {}))

const crowded = layoutSky(
  decorateTopics(Array.from({ length: 10 }, (_, index) => ({ id: index, total_volume_percent: 8 }))),
  8,
)
assert.ok(orbitsClear(crowded), 'same-size planets still get their own lane')

const outer = orbitRadius(9, false)
const extent = systemExtent(10, layout.extent)
assert.ok(extent > layout.radii[9])
for (const isMobile of [false, true]) {
  const home = homeLookAt(isMobile, 10, layout.extent)
  const distance = Math.hypot(home[0], home[1], home[2])
  assert.ok(distance > extent, `home camera too close on ${isMobile ? 'mobile' : 'desktop'}: ${distance}`)
  assert.ok(home[1] > 8)
  assert.ok(home[2] > outer * 0.4)
}

console.log('sky settings, tagline, and texture quality ok')
