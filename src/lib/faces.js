import { Quaternion, Vector3 } from 'three'
import { cubeSpikeFaces, polyhedron } from './polyhedra.js'

export const MIN_FACES = 1
export const MAX_FACES = 6
export const CORE_RADIUS = 0.82

const UP = new Vector3(0, 1, 0)

const SHAPE_NAMES = {
  1: 'Point',
  2: 'Diamond',
  3: 'Prism',
  4: 'Tetrahedron',
  5: 'Pyramid',
  6: 'Cube',
}

export function clampFaceCount(count) {
  const value = Number(count)
  if (!Number.isFinite(value)) return MIN_FACES
  return Math.min(MAX_FACES, Math.max(MIN_FACES, Math.round(value)))
}

export function shapeName(count) {
  return SHAPE_NAMES[clampFaceCount(count)]
}

export function faceLayout(count) {
  const solid = polyhedron(6)
  return cubeSpikeFaces(count).map((faceIndex) => {
    const normal = solid.normals[faceIndex]
    const quaternion = new Quaternion().setFromUnitVectors(UP, normal)
    const position = normal.clone().multiplyScalar(CORE_RADIUS * 0.96)
    return {
      position: [position.x, position.y, position.z],
      quaternion,
      direction: [normal.x, normal.y, normal.z],
      radialSegments: 3,
    }
  })
}
