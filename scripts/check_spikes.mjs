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
assert.ok(spikeProfile(1) < 1e-10)
assert.ok(spikeProfile(0.5) > 0.6)
assert.ok(spikeRounding(1) > spikeRounding(0))
assert.equal(spikeDetail('low').rings, 6)
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
  'high',
)
assert.equal(crystal.faces.length, 6)
assert.deepEqual(crystal.faces.map((face) => face.sides), [4, 4, 4, 4, 4, 4])
for (const face of crystal.faces) {
  assert.ok(face.extrusion.getAttribute('position').count > 16)
  assert.ok(face.extrusion.getIndex().count > 24)
}

const tetra = buildCrystal(
  [
    { id: 'a', volume_percent: 40 },
    { id: 'b', volume_percent: 30 },
    { id: 'c', volume_percent: 20 },
    { id: 'd', volume_percent: 10 },
  ],
  'low',
)
assert.equal(tetra.faces.length, 4)
assert.ok(tetra.faces.every((face) => face.sides === 3))

crystal.core.dispose()
for (const face of crystal.faces) {
  face.extrusion.dispose()
  face.pick.dispose()
}
tetra.core.dispose()
for (const face of tetra.faces) {
  face.extrusion.dispose()
  face.pick.dispose()
}
spike.dispose()

console.log('pencil spikes cover every cube side and taper to a point')
