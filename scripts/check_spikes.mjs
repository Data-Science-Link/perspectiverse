import assert from 'node:assert/strict'
import { Vector3 } from 'three'
import { polyhedron } from '../src/lib/polyhedra.js'
import {
  buildCrystal,
  buildPencilSpike,
  spikeDetail,
  spikeProfile,
  spikeRounding,
} from '../src/lib/spikes.js'

assert.equal(spikeProfile(0), 1)
assert.ok(Math.abs(spikeProfile(1)) < 1e-10)
assert.ok(spikeProfile(0.5) > 0.35 && spikeProfile(0.5) < 0.55)
assert.ok(spikeProfile(0.25) > spikeProfile(0.75))
assert.ok(spikeRounding(1) > spikeRounding(0))
assert.equal(spikeDetail('low').rings, 7)
assert.ok(spikeDetail('high').segsPerEdge > spikeDetail('low').segsPerEdge)

const cube = polyhedron(6)
const loop = cube.faces[0]
const verts = loop.map((index) => cube.vertices[index].clone())
const centroid = verts[0].clone().set(0, 0, 0)
for (const vertex of verts) centroid.add(vertex)
centroid.divideScalar(verts.length)
const normal = cube.normals[0].clone()
const height = 0.9
const detail = spikeDetail('high')
const spike = buildPencilSpike(verts, centroid, normal, height, detail)

const positions = spike.getAttribute('position')
assert.ok(positions.count > verts.length * 4)
assert.ok(spike.getIndex())
const apex = new Vector3().fromBufferAttribute(positions, positions.count - 1)
const expectedApex = centroid.clone().addScaledVector(normal, height)
assert.ok(apex.distanceTo(expectedApex) < 1e-6, 'apex should sit on the face normal')

const first = new Vector3().fromBufferAttribute(positions, 0)
assert.ok(Math.abs(first.clone().sub(centroid).dot(normal)) < 0.02, 'base ring stays on the cube face')

const normals = spike.getAttribute('normal')
const apexNormal = new Vector3().fromBufferAttribute(normals, positions.count - 1)
assert.ok(apexNormal.dot(normal) > 0.35, `spike normals should face outward, got ${apexNormal.dot(normal)}`)

const crystal = buildCrystal(
  [
    { id: 'a', volume_percent: 40 },
    { id: 'b', volume_percent: 22 },
    { id: 'c', volume_percent: 14 },
    { id: 'd', volume_percent: 10 },
    { id: 'e', volume_percent: 8 },
    { id: 'f', volume_percent: 6 },
  ],
  { quality: 'high', pigment: '#f4c14e' },
)
assert.equal(crystal.faces.length, 6)
assert.equal(crystal.empty.length, 0)
assert.ok(crystal.core)
assert.ok(crystal.faces.every((face) => face.sides === 4))
assert.ok(crystal.faces.every((face) => face.opacity === 1))
assert.notEqual(crystal.faces[0].color, crystal.faces[5].color)
assert.ok(crystal.faces[0].color !== '#f4c14e')
assert.ok(crystal.faces[2].color !== crystal.faces[0].color)
for (const face of crystal.faces) {
  assert.ok(face.extrusion.getAttribute('position').count > 16)
  assert.ok(face.extrusion.getIndex().count > 24)
}

const four = buildCrystal(
  [
    { id: 'a', volume_percent: 40 },
    { id: 'b', volume_percent: 30 },
    { id: 'c', volume_percent: 20 },
    { id: 'd', volume_percent: 10 },
  ],
  { quality: 'low', pigment: '#4aa3e6' },
)
assert.equal(four.faces.length, 4)
assert.equal(four.empty.length, 2)
assert.ok(four.empty.every((face) => face.fill.getAttribute('position') && face.dashes.getAttribute('position').count >= 8))
assert.ok(four.faces.every((face) => face.sides === 4))
assert.ok(four.faces.every((face) => face.opacity === 1))

crystal.core.dispose()
crystal.faces.forEach((face) => {
  face.extrusion.dispose()
  face.pick.dispose()
})
four.core.dispose()
four.empty.forEach((face) => {
  face.fill.dispose()
  face.dashes.dispose()
})
four.faces.forEach((face) => {
  face.extrusion.dispose()
  face.pick.dispose()
})
spike.dispose()

console.log('pencil spikes cover every cube side and taper to a point')
