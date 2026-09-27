import { Quaternion, Vector3 } from 'three'

export const MIN_FACES = 2
export const MAX_FACES = 6
export const CORE_RADIUS = 0.82

const UP = new Vector3(0, 1, 0)

const DIRECTIONS = {
  2: [
    [0, 1, 0],
    [0, -1, 0],
  ],
  3: [
    [1, 0.18, 0],
    [-0.5, 0.18, 0.866],
    [-0.5, 0.18, -0.866],
  ],
  4: [
    [1, 1, 1],
    [1, -1, -1],
    [-1, 1, -1],
    [-1, -1, 1],
  ],
  5: [
    [0, 1, 0],
    [0, -1, 0],
    [1, 0, 0],
    [-0.5, 0, 0.866],
    [-0.5, 0, -0.866],
  ],
  6: [
    [0, 1, 0],
    [0, -1, 0],
    [1, 0, 0],
    [-1, 0, 0],
    [0, 0, 1],
    [0, 0, -1],
  ],
}

const SHAPE_NAMES = {
  2: 'Two poles',
  3: 'Triad',
  4: 'Tetrahedron',
  5: 'Bipyramid',
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

function radialSegments(count) {
  if (count <= 5) return 3
  return 4
}

export function faceLayout(count) {
  const n = clampFaceCount(count)
  const segments = radialSegments(n)
  return DIRECTIONS[n].map((dir) => {
    const normal = new Vector3(dir[0], dir[1], dir[2]).normalize()
    const quaternion = new Quaternion().setFromUnitVectors(UP, normal)
    const position = normal.clone().multiplyScalar(CORE_RADIUS * 0.96)
    return {
      position: [position.x, position.y, position.z],
      quaternion,
      direction: [normal.x, normal.y, normal.z],
      radialSegments: segments,
    }
  })
}
