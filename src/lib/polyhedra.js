import { Vector3 } from 'three'

const RADIUS = 0.72
const MIN_FACES = 2
const MAX_FACES = 6

function clampFaceCount(count) {
  const value = Number(count)
  if (!Number.isFinite(value)) return MIN_FACES
  return Math.min(MAX_FACES, Math.max(MIN_FACES, Math.round(value)))
}

function vec(x, y, z) {
  return new Vector3(x, y, z)
}

function scaleToRadius(vertices, radius = RADIUS) {
  let max = 0
  for (const vertex of vertices) {
    max = Math.max(max, vertex.length())
  }
  const factor = max === 0 ? 1 : radius / max
  return vertices.map((vertex) => vertex.multiplyScalar(factor))
}

function centroidOf(vertices, loop) {
  const center = new Vector3()
  for (const index of loop) center.add(vertices[index])
  return center.divideScalar(loop.length)
}

function normalOf(vertices, loop) {
  const a = vertices[loop[0]]
  const b = vertices[loop[1]]
  const c = vertices[loop[2]]
  const normal = new Vector3().subVectors(b, a).cross(new Vector3().subVectors(c, a)).normalize()
  const center = centroidOf(vertices, loop)
  if (normal.dot(center) < 0) normal.negate()
  return normal
}

function solid(rawVertices, faces) {
  const vertices = scaleToRadius(rawVertices.map((vertex) => vertex.clone()))
  const normals = faces.map((loop) => normalOf(vertices, loop))
  return { vertices, faces, normals }
}

function diamond() {
  return solid(
    [
      vec(0, 1, 0),
      vec(0, -1, 0),
      vec(1, 0, 1),
      vec(1, 0, -1),
      vec(-1, 0, -1),
      vec(-1, 0, 1),
    ],
    [
      [2, 3, 4, 5],
      [2, 5, 4, 3],
    ],
  )
}

function prism() {
  return solid(
    [
      vec(1, 0.72, 0),
      vec(-0.5, 0.72, 0.866),
      vec(-0.5, 0.72, -0.866),
      vec(1, -0.72, 0),
      vec(-0.5, -0.72, 0.866),
      vec(-0.5, -0.72, -0.866),
    ],
    [
      [0, 3, 4, 1],
      [1, 4, 5, 2],
      [2, 5, 3, 0],
    ],
  )
}

function tetrahedron() {
  return solid(
    [vec(1, 1, 1), vec(1, -1, -1), vec(-1, 1, -1), vec(-1, -1, 1)],
    [
      [0, 2, 1],
      [0, 1, 3],
      [0, 3, 2],
      [1, 2, 3],
    ],
  )
}

function squarePyramid() {
  return solid(
    [
      vec(0, 1.15, 0),
      vec(1, -0.55, 1),
      vec(1, -0.55, -1),
      vec(-1, -0.55, -1),
      vec(-1, -0.55, 1),
    ],
    [
      [0, 1, 2],
      [0, 2, 3],
      [0, 3, 4],
      [0, 4, 1],
      [1, 4, 3, 2],
    ],
  )
}

function cube() {
  return solid(
    [
      vec(1, 1, 1),
      vec(1, 1, -1),
      vec(1, -1, 1),
      vec(1, -1, -1),
      vec(-1, 1, 1),
      vec(-1, 1, -1),
      vec(-1, -1, 1),
      vec(-1, -1, -1),
    ],
    [
      [0, 1, 5, 4],
      [2, 6, 7, 3],
      [0, 2, 3, 1],
      [4, 5, 7, 6],
      [0, 4, 6, 2],
      [1, 3, 7, 5],
    ],
  )
}

const BUILDERS = {
  2: diamond,
  3: prism,
  4: tetrahedron,
  5: squarePyramid,
  6: cube,
}

const CUBE_SPIKE_FACES = {
  1: [0],
  2: [0, 1],
  3: [0, 2, 4],
  4: [0, 1, 2, 3],
  5: [0, 1, 2, 3, 4],
  6: [0, 1, 2, 3, 4, 5],
}

function clampSpikeCount(count) {
  const value = Number(count)
  if (!Number.isFinite(value)) return 1
  return Math.min(MAX_FACES, Math.max(1, Math.round(value)))
}

export function polyhedron(count) {
  return BUILDERS[clampFaceCount(count)]()
}

export function cubeSpikeFaces(count) {
  return CUBE_SPIKE_FACES[clampSpikeCount(count)]
}

export function faceHeight(volumePercent) {
  return 0.22 + (Number(volumePercent) / 100) * 1.2
}
