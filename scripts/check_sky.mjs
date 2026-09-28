import assert from 'node:assert/strict'
import { SITE_TAGLINE, SITE_TITLE, WELCOME_STORAGE_KEY } from '../src/lib/copy.js'
import { skySettings } from '../src/lib/skySettings.js'
import { TEXTURE_QUALITY, textureSize } from '../src/lib/planetTextures.js'

assert.equal(SITE_TITLE, 'Perspectiverse')
assert.match(SITE_TAGLINE, /perspective/i)
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

console.log('sky settings, tagline, and texture quality ok')
