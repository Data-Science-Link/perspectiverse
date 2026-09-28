import { BufferAttribute, BufferGeometry, Vector3 } from 'three'
import { rankPerspectives, spikeColor } from './colors.js'
import { faceHeight, polyhedron } from './polyhedra.js'

const _from = new Vector3()
const _poly = new Vector3()
const _circle = new Vector3()
const _mixed = new Vector3()
const _apex = new Vector3()

export function spikeDetail(quality = 'high') {
  if (quality === 'low') return { rings: 6, segsPerEdge: 4 }
  if (quality === 'medium') return { rings: 8, segsPerEdge: 5 }
  return { rings: 10, segsPerEdge: 6 }
}

export function spikeProfile(t) {
  const clamped = Math.min(1, Math.max(0, t))
  return Math.cos((clamped * Math.PI) / 2)
}

export function spikeRounding(t) {
  const clamped = Math.min(1, Math.max(0, t))
  return 0.04 + 0.78 * clamped * clamped
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
    const ring = sampleFaceRing(verts, centroid, segsPerEdge, spikeProfile(t), spikeRounding(t))
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

export function buildCrystal(perspectives, quality = 'high') {
  const ranked = rankPerspectives(perspectives)
  const solid = polyhedron(ranked.length)
  const coreTriangles = []
  const detail = spikeDetail(quality)
  const faces = ranked.map((perspective, index) => {
    const loop = solid.faces[index]
    const verts = loop.map((vertexIndex) => solid.vertices[vertexIndex].clone())
    const normal = solid.normals[index].clone()
    const centroid = faceCentroid(verts)
    const height = faceHeight(perspective.volume_percent)
    const pickApex = centroid.clone().addScaledVector(normal, height * 1.25)
    coreTriangles.push(...triangulate(solid.vertices, loop))
    const pick = []
    for (let edge = 0; edge < verts.length; edge += 1) {
      const a = verts[edge]
      const b = verts[(edge + 1) % verts.length]
      pick.push([a, b, pickApex])
    }
    return {
      ...perspective,
      index,
      sides: verts.length,
      color: spikeColor(index),
      direction: [normal.x, normal.y, normal.z],
      extrusion: buildPencilSpike(verts, centroid, normal, height, detail),
      pick: geometryFromTriangles(pick),
    }
  })

  return {
    core: geometryFromTriangles(coreTriangles),
    faces,
  }
}
