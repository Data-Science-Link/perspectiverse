import { CanvasTexture, RepeatWrapping, SRGBColorSpace } from 'three'

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
    const radius = 0.018 + hash(i, 3, seed) * 0.07
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
  const granulation = fbm(nx, ny, 22, 18, 3.2, 6)
  const cell = ridge(nx, ny, 16, 14, 8.4, 4)
  const spot = fbm(nx, ny, 7, 8, 11.4, 4)
  const flare = fbm(nx, ny, 4, 5, 21.6, 3)
  const limb = clamp01(1 - d * 1.12)
  let color = mix([255, 176, 58], [255, 236, 168], clamp01(granulation * 0.55 + cell * 0.35))
  color = mix(color, [255, 98, 28], clamp01(spot * 0.35 + d * 0.28))
  if (spot > 0.78) color = mix(color, [92, 38, 18], (spot - 0.78) * 2.4)
  color = mix(color, [255, 248, 210], flare * 0.18 * limb)
  const dim = 0.48 + limb * 0.62
  return color.map((c) => Math.round(c * dim))
}

function mercuryShade(nx, ny) {
  const plains = fbm(nx, ny, 8, 9, 2.1, 6)
  const grit = fbm(nx, ny, 28, 30, 8.8, 4)
  const crater = craterField(nx, ny, 14.2, 26)
  let color = mix([168, 172, 178], [92, 96, 104], plains)
  color = mix(color, [210, 214, 220], grit * 0.22)
  color = mix(color, [54, 56, 62], clamp01(-crater) * 0.85)
  color = mix(color, [232, 234, 238], clamp01(crater) * 0.7)
  if (ny < 0.08 || ny > 0.92) color = mix(color, [198, 200, 206], 0.25)
  return color
}

function venusShade(nx, ny) {
  const warp = fbm(nx, ny, 3, 4, 4.6, 5)
  const swirl = fbm(nx + warp * 0.18, ny + warp * 0.08, 5, 7, 9.1, 6)
  const streak = 0.5 + 0.5 * Math.sin((ny + swirl * 0.22) * Math.PI * 7)
  let color = mix([255, 214, 148], [240, 176, 96], clamp01(swirl * 0.55 + streak * 0.35))
  color = mix(color, [255, 236, 196], clamp01((1 - swirl) * 0.28))
  const dark = fbm(nx, ny, 2.4, 3.2, 18.4, 3)
  if (dark > 0.72) color = mix(color, [196, 126, 72], (dark - 0.72) * 1.4)
  return color
}

function earthShade(nx, ny) {
  const oceanDeep = [12, 62, 148]
  const oceanShallow = [46, 148, 196]
  const land = [46, 150, 78]
  const forest = [22, 102, 52]
  const desert = [214, 186, 104]
  const ice = [236, 246, 255]
  const depth = fbm(nx, ny, 6, 7, 2.2, 4)
  const cloudWarp = fbm(nx, ny, 4, 5, 19, 4)
  const cloud = fbm(nx + cloudWarp * 0.12, ny, 10, 8, 27, 5)

  let landness = 0
  const blobs = [
    [0.18, 0.34, 0.15, 0.18],
    [0.28, 0.58, 0.1, 0.2],
    [0.48, 0.46, 0.12, 0.22],
    [0.54, 0.28, 0.08, 0.09],
    [0.7, 0.36, 0.2, 0.15],
    [0.84, 0.62, 0.09, 0.08],
    [0.36, 0.14, 0.07, 0.05],
    [0.12, 0.7, 0.07, 0.1],
    [0.92, 0.32, 0.08, 0.1],
  ]
  for (const [cx, cy, rx, ry] of blobs) {
    landness = Math.max(landness, clamp01(1 - ellipse(nx, ny, cx, cy, rx, ry)))
  }
  landness = clamp01(landness + (fbm(nx, ny, 14, 16, 5.5, 3) - 0.5) * 0.28)

  let color = mix(oceanDeep, oceanShallow, clamp01(depth * 0.65 + (1 - Math.abs(ny - 0.5)) * 0.2))
  if (landness > 0.38) {
    const arid = fbm(nx, ny, 7, 7, 5.5, 4)
    const lush = mix(forest, land, fbm(nx, ny, 9, 8, 33, 3))
    color = mix(lush, desert, clamp01(arid * 0.7 - 0.18))
  }
  if (ny < 0.11 || ny > 0.89) color = mix(color, ice, 0.92)
  else if (ny < 0.16 || ny > 0.84) color = mix(color, ice, 0.35)
  if (cloud > 0.62) color = mix(color, [248, 252, 255], clamp01((cloud - 0.62) * 2.1))
  return color
}

function marsShade(nx, ny) {
  const n = fbm(nx, ny, 8, 9, 7.7, 6)
  const canyon = ridge(nx, ny, 5, 11, 3.3, 4)
  const dust = fbm(nx, ny, 18, 16, 15.2, 4)
  const crater = craterField(nx, ny, 6.4, 16)
  let color = mix([196, 72, 36], [236, 140, 78], n)
  color = mix(color, [92, 32, 22], clamp01(canyon * 0.45))
  color = mix(color, [240, 176, 112], dust * 0.18)
  color = mix(color, [62, 24, 18], clamp01(-crater) * 0.55)
  color = mix(color, [240, 196, 150], clamp01(crater) * 0.35)
  if (ny < 0.09 || ny > 0.91) color = mix(color, [248, 244, 236], 0.88)
  return color
}

function jupiterShade(nx, ny) {
  const warp = fbm(nx, ny, 3, 10, 12.2, 5)
  const bands = 0.5 + 0.5 * Math.sin((ny + warp * 0.08) * Math.PI * 16)
  const turbulence = fbm(nx + warp * 0.2, ny, 8, 22, 18.6, 5)
  const cream = [248, 226, 186]
  const amber = [226, 164, 82]
  const rust = [188, 92, 48]
  const white = [255, 244, 226]
  let color = mix(cream, amber, clamp01(bands * 0.75 + turbulence * 0.28))
  if (bands > 0.72) color = mix(color, white, (bands - 0.72) * 1.6)
  if (bands < 0.28) color = mix(color, rust, (0.28 - bands) * 1.3)
  const spot = ellipse(nx, ny, 0.7, 0.62, 0.09, 0.055)
  if (spot < 1) color = mix(color, [214, 72, 52], clamp01(1 - spot) * 0.92)
  return color
}

function saturnShade(nx, ny) {
  const warp = fbm(nx, ny, 2.6, 8, 6.1, 4)
  const bands = 0.5 + 0.5 * Math.sin((ny + warp * 0.05) * Math.PI * 12)
  const n = fbm(nx, ny, 5, 14, 9.4, 4)
  const ivory = [255, 236, 196]
  const champagne = [236, 206, 142]
  const caramel = [210, 168, 96]
  let color = mix(ivory, champagne, clamp01(bands * 0.6 + n * 0.25))
  if (bands < 0.32) color = mix(color, caramel, (0.32 - bands) * 1.1)
  if (ny < 0.12 || ny > 0.88) color = mix(color, [244, 228, 186], 0.28)
  return color
}

function uranusShade(nx, ny) {
  const n = fbm(nx, ny, 4, 6, 2.8, 5)
  const band = 0.5 + 0.5 * Math.sin(ny * Math.PI * 5 + n * 1.4)
  const haze = fbm(nx, ny, 2, 3, 14.8, 3)
  let color = mix([154, 232, 226], [86, 196, 198], clamp01(n * 0.45 + band * 0.2))
  color = mix(color, [210, 250, 246], haze * 0.22)
  if (ny < 0.1 || ny > 0.9) color = mix(color, [232, 252, 250], 0.35)
  return color
}

function neptuneShade(nx, ny) {
  const n = fbm(nx, ny, 5, 7, 9.4, 5)
  const streak = fbm(nx, ny, 9, 3.2, 21.1, 4)
  let color = mix([34, 78, 210], [18, 42, 132], n)
  color = mix(color, [86, 168, 255], clamp01(streak * 0.35))
  if (streak > 0.7) color = mix(color, [230, 242, 255], (streak - 0.7) * 1.5)
  const spot = ellipse(nx, ny, 0.36, 0.4, 0.075, 0.05)
  if (spot < 1) color = mix(color, [12, 24, 86], clamp01(1 - spot) * 0.85)
  return color
}

function plutoShade(nx, ny) {
  const n = fbm(nx, ny, 7, 8, 14.1, 5)
  const grit = fbm(nx, ny, 18, 16, 4.8, 4)
  let color = mix([92, 82, 86], [176, 148, 132], n)
  color = mix(color, [214, 126, 82], clamp01(grit * 0.22))
  const heart = ellipse(nx, ny, 0.58, 0.42, 0.13, 0.11)
  if (heart < 1) color = mix(color, [255, 214, 198], clamp01(1 - heart) * 0.95)
  const ice = ellipse(nx, ny, 0.22, 0.7, 0.1, 0.08)
  if (ice < 1) color = mix(color, [226, 232, 236], clamp01(1 - ice) * 0.7)
  if (ny < 0.08 || ny > 0.92) color = mix(color, [232, 228, 224], 0.4)
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

export function createBodyTexture(key) {
  const shade = SHADERS[key] ?? mercuryShade
  return paintTexture(1024, 512, shade)
}

export function createRingTexture() {
  const size = 512
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
  return texture
}
