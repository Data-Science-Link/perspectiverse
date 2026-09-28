import assert from 'node:assert/strict'
import { SITE_TAGLINE, SITE_TITLE, SOLAR_SYSTEM_LABEL, WELCOME_STORAGE_KEY } from '../src/lib/copy.js'
import { skySettings } from '../src/lib/skySettings.js'
import { TEXTURE_QUALITY, textureSize } from '../src/lib/planetTextures.js'
import { homeLookAt, orbitRadius, systemExtent } from '../src/lib/layout.js'

assert.equal(SITE_TITLE, 'Perspectiverse')
assert.match(SITE_TAGLINE, /perspective/i)
assert.equal(SOLAR_SYSTEM_LABEL, 'Solar System')
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

const outer = orbitRadius(9, false)
const extent = systemExtent(10)
assert.ok(extent > outer)
for (const mobile of [false, true]) {
  const home = homeLookAt(mobile, 10)
  const distance = Math.hypot(home[0], home[1], home[2])
  assert.ok(distance > extent, `home camera too close on ${mobile ? 'mobile' : 'desktop'}: ${distance}`)
  assert.ok(home[1] > 8)
  assert.ok(home[2] > outer)
}

console.log('sky settings, tagline, and texture quality ok')
