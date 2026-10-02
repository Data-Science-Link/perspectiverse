import { CanvasTexture, RepeatWrapping, SRGBColorSpace } from 'three'
import { shadeHex } from './colors.js'

function hash(ix, iy, seed) {
  const n = Math.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453123
  return n - Math.floor(n)
}

function lerp(a, b, t) {
  return a + (b - a) * t
}

function mix([ar, ag, ab], [br, bg, bb], t) {
  return [lerp(ar, br, t), lerp(ag, bg, t), lerp(ab, bb, t)]
}

function clamp01(value) {
  return Math.min(1, Math.max(0, value))
}

function fade(t) {
  return t * t * t * (t * (t * 6 - 15) + 10)
}

function wrapDelta(dx) {
  if (dx > 0.5) return dx - 1
  if (dx < -0.5) return dx + 1
  return dx
}

function valueNoise(x, y, seed, wrapX = 0) {
  const x0 = Math.floor(x)
  const y0 = Math.floor(y)
  const fx = fade(x - x0)
  const fy = fade(y - y0)
  const x1 = x0 + 1
  const wx0 = wrapX > 0 ? ((x0 % wrapX) + wrapX) % wrapX : x0
  const wx1 = wrapX > 0 ? ((x1 % wrapX) + wrapX) % wrapX : x1
  const a = hash(wx0, y0, seed)
  const b = hash(wx1, y0, seed)
  const c = hash(wx0, y0 + 1, seed)
  const d = hash(wx1, y0 + 1, seed)
  return lerp(lerp(a, b, fx), lerp(c, d, fx), fy)
}

function fbm(nx, ny, scaleX, scaleY, seed, octaves = 5) {
  let total = 0
  let amplitude = 0.5
  let frequency = 1
  let sum = 0
  let period = scaleX
  for (let i = 0; i < octaves; i += 1) {
    total += valueNoise(nx * scaleX * frequency, ny * scaleY * frequency, seed + i * 19.1, period) * amplitude
    sum += amplitude
    amplitude *= 0.5
    frequency *= 2
    period *= 2
  }
  return total / sum
}

function ridge(nx, ny, scaleX, scaleY, seed, octaves = 4) {
  const n = fbm(nx, ny, scaleX, scaleY, seed, octaves)
  return 1 - Math.abs(n * 2 - 1)
}

function ellipse(nx, ny, cx, cy, rx, ry) {
  const dx = wrapDelta(nx - cx) / rx
  const dy = (ny - cy) / ry
  return dx * dx + dy * dy
}

function craterField(nx, ny, seed, count = 22) {
  let shade = 0
  for (let i = 0; i < count; i += 1) {
    const cx = hash(i, 1, seed)
    const cy = 0.08 + hash(i, 2, seed) * 0.84
    const radius = 0.04 + hash(i, 3, seed) * 0.12
    const d = Math.hypot(wrapDelta(nx - cx), ny - cy) / radius
    if (d >= 1.15) continue
    const rim = Math.exp(-((d - 0.8) ** 2) * 48)
    const bowl = clamp01(1 - d) ** 2
    shade += rim * 0.7 - bowl * 0.72
  }
  return shade
}

function paintTexture(width, height, shade) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  const image = ctx.createImageData(width, height)
  const data = image.data

  for (let y = 0; y < height; y += 1) {
    const ny = y / (height - 1)
    for (let x = 0; x < width; x += 1) {
      const nx = x / (width - 1)
      const [r, g, b] = shade(nx, ny)
      const i = (y * width + x) * 4
      data[i] = r
      data[i + 1] = g
      data[i + 2] = b
      data[i + 3] = 255
    }
  }

  ctx.putImageData(image, 0, 0)
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  texture.wrapS = RepeatWrapping
  texture.needsUpdate = true
  return texture
}

function sunShade(nx, ny) {
  const d = Math.hypot(wrapDelta(nx - 0.5), ny - 0.5)
  const granulation = fbm(nx, ny, 10, 9, 3.2, 5)
  const cell = ridge(nx, ny, 8, 7, 8.4, 3)
  const spot = fbm(nx, ny, 5, 6, 11.4, 4)
  const flare = fbm(nx, ny, 3, 3.5, 21.6, 3)
  const limb = clamp01(1 - d * 0.92)
  let color = mix([255, 168, 42], [255, 236, 148], clamp01(granulation * 0.7 + cell * 0.45))
  color = mix(color, [255, 252, 232], clamp01(flare * 0.55) * limb)
  if (spot > 0.8) color = mix(color, [168, 72, 22], (spot - 0.8) * 1.5)
  const dim = 0.82 + limb * 0.22
  return color.map((c) => Math.round(c * dim))
}

function mercuryShade(nx, ny) {
  const plains = fbm(nx, ny, 5, 6, 2.1, 5)
  const grit = fbm(nx, ny, 16, 18, 8.8, 4)
  const crater = craterField(nx, ny, 14.2, 18)
  let color = mix([196, 200, 208], [78, 82, 90], plains)
  color = mix(color, [230, 232, 236], grit * 0.28)
  color = mix(color, [40, 42, 48], clamp01(-crater))
  color = mix(color, [236, 238, 242], clamp01(crater) * 0.85)
  return color
}

function venusShade(nx, ny) {
  const warp = fbm(nx, ny, 2.2, 3, 4.6, 4)
  const swirl = fbm(nx + warp * 0.28, ny + warp * 0.1, 3.4, 5, 9.1, 5)
  const streak = 0.5 + 0.5 * Math.sin((ny + swirl * 0.28) * Math.PI * 5)
  let color = mix([255, 232, 168], [232, 148, 64], clamp01(swirl * 0.7 + streak * 0.45))
  color = mix(color, [255, 248, 220], clamp01((1 - swirl) * 0.42))
  if (streak > 0.72) color = mix(color, [255, 210, 120], (streak - 0.72) * 1.6)
  return color
}

function earthShade(nx, ny) {
  const oceanDeep = [8, 48, 132]
  const oceanShallow = [42, 156, 206]
  const land = [72, 168, 74]
  const forest = [18, 96, 42]
  const desert = [222, 188, 92]
  const ice = [244, 250, 255]
  const depth = fbm(nx, ny, 4, 5, 2.2, 3)
  const cloudWarp = fbm(nx, ny, 3, 3.5, 19, 3)
  const cloud = fbm(nx + cloudWarp * 0.16, ny, 6, 5, 27, 4)

  let landness = 0
  const blobs = [
    [0.2, 0.36, 0.2, 0.22],
    [0.3, 0.58, 0.14, 0.24],
    [0.5, 0.44, 0.16, 0.26],
    [0.56, 0.26, 0.11, 0.12],
    [0.72, 0.34, 0.24, 0.18],
    [0.86, 0.62, 0.12, 0.1],
    [0.14, 0.7, 0.1, 0.14],
    [0.9, 0.3, 0.1, 0.12],
  ]
  for (const [cx, cy, rx, ry] of blobs) {
    landness = Math.max(landness, clamp01(1 - ellipse(nx, ny, cx, cy, rx, ry)))
  }
  landness = clamp01(landness + (fbm(nx, ny, 8, 9, 5.5, 3) - 0.5) * 0.22)

  let color = mix(oceanDeep, oceanShallow, clamp01(depth * 0.7 + (1 - Math.abs(ny - 0.5)) * 0.25))
  if (landness > 0.32) {
    const arid = fbm(nx, ny, 5, 5, 5.5, 3)
    const lush = mix(forest, land, fbm(nx, ny, 6, 5, 33, 3))
    color = mix(lush, desert, clamp01(arid * 0.75 - 0.15))
  }
  if (ny < 0.12 || ny > 0.88) color = ice
  else if (ny < 0.18 || ny > 0.82) color = mix(color, ice, 0.55)
  if (cloud > 0.58) color = mix(color, [255, 255, 255], clamp01((cloud - 0.58) * 2.4))
  return color
}

function marsShade(nx, ny) {
  const n = fbm(nx, ny, 5, 6, 7.7, 5)
  const canyon = ridge(nx, ny, 3.4, 8, 3.3, 3)
  const dust = fbm(nx, ny, 10, 9, 15.2, 3)
  const crater = craterField(nx, ny, 6.4, 12)
  let color = mix([168, 40, 18], [244, 150, 72], n)
  color = mix(color, [72, 22, 16], clamp01(canyon * 0.65))
  color = mix(color, [246, 186, 110], dust * 0.28)
  color = mix(color, [48, 18, 14], clamp01(-crater) * 0.75)
  color = mix(color, [246, 206, 160], clamp01(crater) * 0.45)
  if (ny < 0.11 || ny > 0.89) color = mix(color, [248, 244, 236], 0.92)
  return color
}

function jupiterShade(nx, ny) {
  const warp = fbm(nx, ny, 2, 6, 12.2, 4)
  const y = ny + warp * 0.07
  const bands = 0.5 + 0.5 * Math.sin(y * Math.PI * 8)
  const turbulence = fbm(nx + warp * 0.25, ny, 5, 14, 18.6, 4)
  const cream = [255, 232, 186]
  const amber = [232, 148, 58]
  const rust = [176, 70, 32]
  const white = [255, 248, 230]
  let color = mix(cream, amber, clamp01(bands * 0.85 + turbulence * 0.2))
  if (bands > 0.62) color = mix(color, white, (bands - 0.62) * 2)
  if (bands < 0.38) color = mix(color, rust, (0.38 - bands) * 1.8)
  const spot = ellipse(nx, ny, 0.7, 0.62, 0.11, 0.07)
  if (spot < 1) color = mix(color, [220, 56, 40], clamp01(1 - spot))
  return color
}

function saturnShade(nx, ny) {
  const warp = fbm(nx, ny, 2, 6, 6.1, 3)
  const bands = 0.5 + 0.5 * Math.sin((ny + warp * 0.05) * Math.PI * 9)
  const n = fbm(nx, ny, 3.5, 10, 9.4, 3)
  const ivory = [255, 242, 204]
  const champagne = [236, 196, 118]
  const caramel = [196, 142, 64]
  let color = mix(ivory, champagne, clamp01(bands * 0.75 + n * 0.22))
  if (bands < 0.36) color = mix(color, caramel, (0.36 - bands) * 1.5)
  if (bands > 0.7) color = mix(color, [255, 250, 230], (bands - 0.7) * 1.6)
  return color
}

function uranusShade(nx, ny) {
  const n = fbm(nx, ny, 3, 4, 2.8, 4)
  const band = 0.5 + 0.5 * Math.sin(ny * Math.PI * 4 + n * 1.6)
  const haze = fbm(nx, ny, 2, 2.4, 14.8, 3)
  let color = mix([120, 228, 220], [46, 168, 176], clamp01(n * 0.55 + band * 0.35))
  color = mix(color, [220, 255, 250], haze * 0.32)
  if (ny < 0.12 || ny > 0.88) color = mix(color, [236, 255, 252], 0.45)
  return color
}

function neptuneShade(nx, ny) {
  const n = fbm(nx, ny, 3.5, 5, 9.4, 4)
  const streak = fbm(nx, ny, 6, 2.2, 21.1, 3)
  let color = mix([18, 64, 220], [8, 24, 110], n)
  color = mix(color, [96, 176, 255], clamp01(streak * 0.5))
  if (streak > 0.62) color = mix(color, [236, 246, 255], (streak - 0.62) * 1.8)
  const spot = ellipse(nx, ny, 0.36, 0.4, 0.09, 0.06)
  if (spot < 1) color = mix(color, [6, 14, 72], clamp01(1 - spot))
  return color
}

function plutoShade(nx, ny) {
  const n = fbm(nx, ny, 4.5, 5, 14.1, 4)
  const grit = fbm(nx, ny, 10, 9, 4.8, 3)
  let color = mix([64, 58, 66], [186, 150, 128], n)
  color = mix(color, [220, 110, 64], clamp01(grit * 0.35))
  const heart = ellipse(nx, ny, 0.58, 0.42, 0.16, 0.14)
  if (heart < 1) color = mix(color, [255, 208, 188], clamp01(1 - heart))
  const ice = ellipse(nx, ny, 0.22, 0.7, 0.12, 0.1)
  if (ice < 1) color = mix(color, [230, 236, 240], clamp01(1 - ice) * 0.85)
  if (ny < 0.1 || ny > 0.9) color = mix(color, [236, 232, 228], 0.5)
  return color
}

const SHADERS = {
  sun: sunShade,
  mercury: mercuryShade,
  venus: venusShade,
  earth: earthShade,
  mars: marsShade,
  jupiter: jupiterShade,
  saturn: saturnShade,
  uranus: uranusShade,
  neptune: neptuneShade,
  pluto: plutoShade,
}

export const TEXTURE_QUALITY = {
  high: { body: [512, 256], ring: 384 },
  medium: { body: [384, 192], ring: 256 },
  low: { body: [256, 128], ring: 192 },
}

const bodyCache = new Map()
const ringCache = new Map()

export function textureSize(quality = 'high') {
  return TEXTURE_QUALITY[quality]?.body ?? TEXTURE_QUALITY.high.body
}

export function createBodyTexture(key, quality = 'high') {
  const shade = SHADERS[key] ?? mercuryShade
  const cacheKey = `${key}:${quality}`
  const hit = bodyCache.get(cacheKey)
  if (hit) return hit
  const [width, height] = textureSize(quality)
  const texture = paintTexture(width, height, shade)
  bodyCache.set(cacheKey, texture)
  return texture
}

export function createRingTexture(quality = 'high') {
  const hit = ringCache.get(quality)
  if (hit) return hit
  const size = TEXTURE_QUALITY[quality]?.ring ?? TEXTURE_QUALITY.high.ring
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  const image = ctx.createImageData(size, size)
  const data = image.data
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = (x - cx) / cx
      const dy = (y - cy) / cy
      const r = Math.hypot(dx, dy)
      const i = (y * size + x) * 4
      if (r < 0.42 || r > 0.98) {
        data[i + 3] = 0
        continue
      }
      const ring = 0.5 + 0.5 * Math.sin(r * 86)
      const fine = 0.5 + 0.5 * Math.sin(r * 240 + hash(x, y, 3.1) * 2)
      const cassini = Math.abs(r - 0.68) < 0.028 ? 0.06 : 1
      const warm = 0.5 + 0.5 * Math.sin(r * 18)
      data[i] = Math.round(210 + ring * 40 + warm * 10)
      data[i + 1] = Math.round(188 + ring * 36)
      data[i + 2] = Math.round(132 + ring * 28 + fine * 8)
      data[i + 3] = Math.round(180 * cassini * (0.42 + ring * 0.45 + fine * 0.12))
    }
  }

  ctx.putImageData(image, 0, 0)
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  texture.needsUpdate = true
  ringCache.set(quality, texture)
  return texture
}

export function createDashTexture(hex) {
  if (typeof document === 'undefined') return null
  const canvas = document.createElement('canvas')
  canvas.width = 128
  canvas.height = 128
  const context = canvas.getContext('2d')
  context.fillStyle = hex || '#9aa3b5'
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.strokeStyle = shadeHex(hex, 0.55)
  context.lineWidth = 5
  context.setLineDash([14, 10])
  for (let offset = -128; offset <= 256; offset += 22) {
    context.beginPath()
    context.moveTo(offset, canvas.height)
    context.lineTo(offset + canvas.width, 0)
    context.stroke()
  }
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  texture.needsUpdate = true
  return texture
}
