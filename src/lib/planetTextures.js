import { CanvasTexture, SRGBColorSpace } from 'three'

function hash(x, y, seed) {
  const n = Math.sin(x * 12.9898 + y * 78.233 + seed * 45.164) * 43758.5453
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

function fbm(x, y, seed, octaves = 4) {
  let total = 0
  let amplitude = 0.5
  let frequency = 1
  let sum = 0
  for (let i = 0; i < octaves; i += 1) {
    total += hash(x * frequency, y * frequency, seed + i * 17) * amplitude
    sum += amplitude
    amplitude *= 0.5
    frequency *= 2
  }
  return total / sum
}

function ellipse(nx, ny, cx, cy, rx, ry) {
  const dx = (nx - cx) / rx
  const dy = (ny - cy) / ry
  return dx * dx + dy * dy
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
      const [r, g, b] = shade(nx, ny, x, y)
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
  texture.needsUpdate = true
  return texture
}

function sunShade(nx, ny) {
  const d = Math.hypot(nx - 0.5, ny - 0.5)
  const granulation = fbm(nx * 18, ny * 18, 3.2, 5)
  const spot = fbm(nx * 7, ny * 9, 11.4, 3)
  const limb = clamp01(1 - d * 1.15)
  const fire = mix([255, 210, 92], [255, 120, 32], clamp01(spot * 0.7 + d * 0.45))
  const color = mix(fire, [255, 246, 180], granulation * 0.45 * limb)
  return color.map((c) => Math.round(c * (0.55 + limb * 0.5)))
}

function mercuryShade(nx, ny) {
  const n = fbm(nx * 10, ny * 12, 2.1, 5)
  const crater = fbm(nx * 28, ny * 30, 8.8, 3)
  const base = mix([118, 108, 98], [186, 176, 164], n)
  if (crater > 0.72) return mix(base, [72, 66, 60], (crater - 0.72) * 3)
  return base
}

function venusShade(nx, ny) {
  const swirl = fbm(nx * 4 + ny * 2.4, ny * 6, 4.6, 5)
  const band = 0.5 + 0.5 * Math.sin((ny + swirl * 0.2) * Math.PI * 6)
  return mix([232, 196, 122], [196, 148, 72], clamp01(band * 0.55 + swirl * 0.35))
}

function earthShade(nx, ny) {
  const ocean = [28, 78, 168]
  const land = [52, 148, 68]
  const desert = [210, 176, 86]
  const ice = [236, 244, 250]
  const cloud = fbm(nx * 9, ny * 11, 19, 4)

  let landness = 0
  const blobs = [
    [0.22, 0.36, 0.16, 0.16],
    [0.3, 0.62, 0.08, 0.16],
    [0.5, 0.48, 0.1, 0.2],
    [0.52, 0.3, 0.08, 0.08],
    [0.7, 0.34, 0.2, 0.14],
    [0.82, 0.66, 0.08, 0.06],
    [0.34, 0.16, 0.06, 0.05],
  ]
  for (const [cx, cy, rx, ry] of blobs) {
    const d = ellipse(nx, ny, cx, cy, rx, ry)
    landness = Math.max(landness, clamp01(1 - d))
  }

  const polar = ny < 0.1 || ny > 0.9 ? 1 : 0
  let color = ocean
  if (landness > 0.35) {
    const arid = fbm(nx * 6, ny * 6, 5.5, 3)
    color = mix(land, desert, arid * 0.55)
  }
  if (polar) color = ice
  if (cloud > 0.68) color = mix(color, [245, 248, 255], 0.55)
  return color
}

function marsShade(nx, ny) {
  const n = fbm(nx * 8, ny * 9, 7.7, 5)
  const base = mix([176, 48, 22], [226, 108, 48], n)
  const dark = fbm(nx * 5, ny * 6, 3.3, 3)
  let color = dark > 0.7 ? mix(base, [92, 36, 20], 0.45) : base
  if (ny < 0.08 || ny > 0.92) color = mix(color, [245, 236, 220], 0.8)
  return color
}

function jupiterShade(nx, ny) {
  const bands = 0.5 + 0.5 * Math.sin(ny * Math.PI * 14)
  const turbulence = fbm(nx * 6, ny * 18, 12.2, 4)
  const base = mix([226, 172, 92], [150, 92, 48], clamp01(bands * 0.8 + turbulence * 0.28))
  const spot = ellipse(nx, ny, 0.72, 0.6, 0.08, 0.05)
  if (spot < 1) return mix(base, [196, 78, 48], clamp01(1 - spot))
  return base
}

function saturnShade(nx, ny) {
  const bands = 0.5 + 0.5 * Math.sin(ny * Math.PI * 10)
  const n = fbm(nx * 4, ny * 12, 6.1, 3)
  return mix([232, 214, 164], [196, 168, 110], clamp01(bands * 0.55 + n * 0.25))
}

function uranusShade(nx, ny) {
  const n = fbm(nx * 3, ny * 5, 2.8, 3)
  const band = 0.5 + 0.5 * Math.sin(ny * Math.PI * 4)
  return mix([126, 206, 210], [86, 168, 176], clamp01(band * 0.25 + n * 0.2))
}

function neptuneShade(nx, ny) {
  const n = fbm(nx * 5, ny * 7, 9.4, 4)
  const base = mix([42, 86, 196], [28, 54, 140], n)
  const spot = ellipse(nx, ny, 0.38, 0.42, 0.07, 0.045)
  if (spot < 1) return mix(base, [18, 36, 92], clamp01(1 - spot) * 0.8)
  return base
}

function plutoShade(nx, ny) {
  const n = fbm(nx * 7, ny * 8, 14.1, 4)
  const base = mix([168, 140, 108], [214, 186, 150], n)
  const heart = ellipse(nx, ny, 0.58, 0.42, 0.12, 0.1)
  if (heart < 1) return mix(base, [236, 214, 196], clamp01(1 - heart))
  return base
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
  return paintTexture(512, 256, shade)
}

export function createRingTexture() {
  const size = 256
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
      const ring = 0.5 + 0.5 * Math.sin(r * 72)
      const cassini = Math.abs(r - 0.68) < 0.03 ? 0.08 : 1
      const shade = 180 + ring * 50
      data[i] = shade
      data[i + 1] = shade - 12
      data[i + 2] = shade - 36
      data[i + 3] = Math.round(165 * cassini * (0.45 + ring * 0.4))
    }
  }

  ctx.putImageData(image, 0, 0)
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  texture.needsUpdate = true
  return texture
}
