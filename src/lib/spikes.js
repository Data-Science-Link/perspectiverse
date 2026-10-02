import { BufferAttribute, BufferGeometry, Vector3 } from 'three'
import { faceShade, rankPerspectives } from './colors.js'
import { cubeSpikeFaces, faceHeight, polyhedron } from './polyhedra.js'

const _from = new Vector3()
const _poly = new Vector3()
const _circle = new Vector3()
const _mixed = new Vector3()
const _apex = new Vector3()

export function spikeDetail(quality = 'high') {
  if (quality === 'low') return { rings: 7, segsPerEdge: 5 }
  if (quality === 'medium') return { rings: 9, segsPerEdge: 6 }
  return { rings: 12, segsPerEdge: 8 }
}

export function spikeProfile(t) {
  const x = Math.min(1, Math.max(0, t))
  // Mostly linear, like a pencil point, with a little extra inset so the
  // join with the cube is not a hard crease.
  return 1 - 1.08 * x + 0.08 * x * x
}

export function spikeRounding(t) {
  const x = Math.min(1, Math.max(0, t))
  return Math.min(0.88, 0.05 + 1.35 * x * x)
}

function faceCentroid(vertices) {
  const centroid = vertices[0].clone().set(0, 0, 0)
  for (const vertex of vertices) centroid.add(vertex)
  return centroid.divideScalar(vertices.length)
}

function meanRadius(verts, centroid) {
  let total = 0
  for (const vertex of verts) total += vertex.distanceTo(centroid)
  return total / verts.length
}

function sampleFaceRing(verts, centroid, segsPerEdge, radiusScale, rounding) {
  const count = verts.length
  const points = []
  const circleR = meanRadius(verts, centroid)

  for (let i = 0; i < count; i += 1) {
    const a = verts[i]
    const b = verts[(i + 1) % count]
    for (let s = 0; s < segsPerEdge; s += 1) {
      const f = s / segsPerEdge
      _poly.copy(a).lerp(b, f)
      _from.copy(_poly).sub(centroid)
      const dist = _from.length() || 1
      _circle.copy(centroid).addScaledVector(_from, circleR / dist)
      const cornerness = 1 - Math.sin(f * Math.PI)
      _mixed.copy(_poly).lerp(_circle, rounding * cornerness)
      _mixed.sub(centroid).multiplyScalar(radiusScale).add(centroid)
      points.push(_mixed.clone())
    }
  }
  return points
}

function geometryFromIndexed(positions, indices) {
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  return geometry
}

function pushTriangle(target, a, b, c) {
  target.push(a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z)
}

function triangulate(vertices, loop) {
  const triangles = []
  for (let index = 1; index < loop.length - 1; index += 1) {
    triangles.push([vertices[loop[0]], vertices[loop[index]], vertices[loop[index + 1]]])
  }
  return triangles
}

function geometryFromTriangles(triangles) {
  const positions = []
  for (const [a, b, c] of triangles) pushTriangle(positions, a, b, c)
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
  geometry.computeVertexNormals()
  return geometry
}

export function buildPencilSpike(verts, centroid, normal, height, { rings, segsPerEdge } = spikeDetail()) {
  const radial = verts.length * segsPerEdge
  const positions = []
  const indices = []
  const ringCount = rings

  for (let r = 0; r < ringCount; r += 1) {
    const t = r / rings
    const radiusScale = Math.max(spikeProfile(t), 0.018)
    const ring = sampleFaceRing(verts, centroid, segsPerEdge, radiusScale, spikeRounding(t))
    const along = height * t
    for (const point of ring) {
      point.addScaledVector(normal, along)
      positions.push(point.x, point.y, point.z)
    }
  }

  _apex.copy(centroid).addScaledVector(normal, height)
  const apexIndex = positions.length / 3
  positions.push(_apex.x, _apex.y, _apex.z)

  for (let r = 0; r < ringCount - 1; r += 1) {
    for (let i = 0; i < radial; i += 1) {
      const i0 = r * radial + i
      const i1 = r * radial + ((i + 1) % radial)
      const j0 = (r + 1) * radial + i
      const j1 = (r + 1) * radial + ((i + 1) % radial)
      indices.push(i0, j0, j1, i0, j1, i1)
    }
  }

  const last = (ringCount - 1) * radial
  for (let i = 0; i < radial; i += 1) {
    const a = last + i
    const b = last + ((i + 1) % radial)
    indices.push(a, b, apexIndex)
  }

  return geometryFromIndexed(positions, indices)
}

const FACE_UVS = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
]

function buildFlatFace(vertices, loop, normal) {
  const lifted = loop.map((vertexIndex) => vertices[vertexIndex].clone().addScaledVector(normal, 0.02))
  const positions = []
  const uvs = []
  const triangles = lifted.length === 4
    ? [[0, 1, 2], [0, 2, 3]]
    : triangulate(lifted, lifted.map((_, index) => index)).map((triangle) => (
      triangle.map((vertex) => lifted.indexOf(vertex))
    ))
  for (const [a, b, c] of triangles) {
    for (const index of [a, b, c]) {
      const vertex = lifted[index]
      const uv = FACE_UVS[index] ?? [0.5, 0.5]
      positions.push(vertex.x, vertex.y, vertex.z)
      uvs.push(uv[0], uv[1])
    }
  }
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
  geometry.setAttribute('uv', new BufferAttribute(new Float32Array(uvs), 2))
  geometry.computeVertexNormals()
  return geometry
}

export function buildCrystal(perspectives, { quality = 'high', pigment = '#f4c14e' } = {}) {
  const ranked = rankPerspectives(perspectives)
  const solid = polyhedron(6)
  const spikeFaces = cubeSpikeFaces(ranked.length)
  const occupied = new Set(spikeFaces)
  const detail = spikeDetail(quality)
  const coreTriangles = []
  const empty = []
  solid.faces.forEach((loop, faceIndex) => {
    if (!occupied.has(faceIndex)) {
      empty.push(buildFlatFace(solid.vertices, loop, solid.normals[faceIndex]))
      return
    }
    coreTriangles.push(...triangulate(solid.vertices, loop))
  })

  const faces = ranked.map((perspective, index) => {
    const faceIndex = spikeFaces[index]
    const loop = solid.faces[faceIndex]
    const verts = loop.map((vertexIndex) => solid.vertices[vertexIndex].clone())
    const normal = solid.normals[faceIndex].clone()
    const centroid = faceCentroid(verts)
    const height = faceHeight(perspective.volume_percent)
    const lifted = verts.map((vertex) => vertex.clone().addScaledVector(normal, 0.018))
    const liftedCentroid = centroid.clone().addScaledVector(normal, 0.018)
    const pickApex = liftedCentroid.clone().addScaledVector(normal, height * 1.18)
    const pick = []
    for (let edge = 0; edge < lifted.length; edge += 1) {
      const a = lifted[edge]
      const b = lifted[(edge + 1) % lifted.length]
      pick.push([a, b, pickApex])
    }
    return {
      ...perspective,
      index,
      sides: lifted.length,
      color: faceShade(pigment, index, ranked.length),
      opacity: 1,
      direction: [normal.x, normal.y, normal.z],
      extrusion: buildPencilSpike(lifted, liftedCentroid, normal, height, detail),
      pick: geometryFromTriangles(pick),
    }
  })

  return {
    core: geometryFromTriangles(coreTriangles),
    empty,
    faces,
  }
}
