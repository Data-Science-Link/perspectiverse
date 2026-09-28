import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { BufferAttribute, BufferGeometry, DoubleSide } from 'three'
import { rankPerspectives, spikeColor } from '../lib/colors'
import { CORE_RADIUS } from '../lib/faces'
import { createBodyTexture, createRingTexture } from '../lib/planetTextures'
import { faceHeight, polyhedron } from '../lib/polyhedra'

function SaturnRings({ meshRef }) {
  const texture = useMemo(() => createRingTexture(), [])
  useEffect(() => () => texture.dispose(), [texture])

  return (
    <mesh ref={meshRef} rotation={[Math.PI / 2.15, 0.18, 0]} raycast={() => null}>
      <ringGeometry args={[1.02, 1.72, 80]} />
      <meshBasicMaterial
        map={texture}
        transparent
        opacity={0.92}
        side={DoubleSide}
        depthWrite={false}
      />
    </mesh>
  )
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

function faceCentroid(vertices) {
  const centroid = vertices[0].clone().set(0, 0, 0)
  for (const vertex of vertices) centroid.add(vertex)
  return centroid.divideScalar(vertices.length)
}

function buildCrystal(perspectives) {
  const ranked = rankPerspectives(perspectives)
  const solid = polyhedron(ranked.length)
  const coreTriangles = []
  const faces = ranked.map((perspective, index) => {
    const loop = solid.faces[index]
    const verts = loop.map((vertexIndex) => solid.vertices[vertexIndex].clone())
    const normal = solid.normals[index].clone()
    const centroid = faceCentroid(verts)
    const height = faceHeight(perspective.volume_percent)
    const apex = centroid.clone().addScaledVector(normal, height)
    const pickApex = centroid.clone().addScaledVector(normal, height * 1.25)
    coreTriangles.push(...triangulate(solid.vertices, loop))
    const extrusion = []
    const pick = []
    for (let edge = 0; edge < verts.length; edge += 1) {
      const a = verts[edge]
      const b = verts[(edge + 1) % verts.length]
      extrusion.push([a, b, apex])
      pick.push([a, b, pickApex])
    }
    return {
      ...perspective,
      index,
      color: spikeColor(index),
      direction: [normal.x, normal.y, normal.z],
      extrusion: geometryFromTriangles(extrusion),
      pick: geometryFromTriangles(pick),
    }
  })

  return {
    core: geometryFromTriangles(coreTriangles),
    faces,
  }
}

export default function SpikyCube({
  perspectives = [],
  body = null,
  coreColor = '#f4c14e',
  selectedPerspectiveId = null,
  dimmed = false,
  showSpikes = true,
  onSelectPerspective,
  interactive = true,
}) {
  const reveal = useRef(showSpikes ? 1 : 0)
  const sphereMat = useRef()
  const sphereMesh = useRef()
  const crystal = useRef()
  const ringMat = useRef()
  const ringMesh = useRef()

  const texture = useMemo(
    () => createBodyTexture(body?.key ?? 'mercury'),
    [body?.key],
  )
  const crystalGeo = useMemo(() => buildCrystal(perspectives), [perspectives])

  useEffect(() => () => {
    texture.dispose()
    crystalGeo.core.dispose()
    for (const face of crystalGeo.faces) {
      face.extrusion.dispose()
      face.pick.dispose()
    }
  }, [texture, crystalGeo])

  useFrame((_, delta) => {
    const target = showSpikes && !dimmed ? 1 : 0
    reveal.current += (target - reveal.current) * Math.min(1, delta * 7)
    const amount = reveal.current
    if (sphereMat.current) {
      sphereMat.current.opacity = dimmed ? 0.16 : 1 - amount
      sphereMat.current.transparent = true
      sphereMat.current.depthWrite = amount < 0.65
    }
    if (sphereMesh.current) {
      const swell = 1 + amount * 0.18
      sphereMesh.current.scale.setScalar(swell)
      sphereMesh.current.visible = amount < 0.97
    }
    if (crystal.current) {
      crystal.current.visible = amount > 0.03
      crystal.current.scale.setScalar(0.72 + amount * 0.28)
    }
    if (ringMat.current) {
      ringMat.current.opacity = (1 - amount) * 0.92
    }
    if (ringMesh.current) {
      ringMesh.current.visible = !dimmed && amount < 0.97
    }
  })

  const color = body?.color ?? coreColor
  const isSun = body?.key === 'sun'
  const emissive = dimmed ? 0.02 : isSun ? 1.15 : 0.035
  const emissiveColor = dimmed ? '#6b7280' : isSun ? color : '#fff4dc'

  return (
    <group>
      <mesh ref={sphereMesh}>
        <sphereGeometry args={[CORE_RADIUS, 64, 48]} />
        <meshStandardMaterial
          ref={sphereMat}
          map={texture}
          color={dimmed ? '#6b7280' : '#ffffff'}
          emissive={emissiveColor}
          emissiveIntensity={emissive}
          roughness={isSun ? 0.28 : body?.key === 'mercury' ? 0.48 : 0.58}
          metalness={isSun ? 0.02 : body?.key === 'mercury' ? 0.22 : 0.06}
          transparent
          opacity={dimmed ? 0.16 : 1}
        />
      </mesh>
      {body?.rings && (
        <SaturnRings
          meshRef={(node) => {
            ringMesh.current = node
            ringMat.current = node?.material ?? null
          }}
        />
      )}
      <group ref={crystal}>
        <mesh geometry={crystalGeo.core} raycast={() => null}>
          <meshStandardMaterial
            color="#161822"
            emissive="#f4c14e"
            emissiveIntensity={0.08}
            roughness={0.42}
            metalness={0.22}
            flatShading
          />
        </mesh>
        {crystalGeo.faces.map((face) => {
          const selected = selectedPerspectiveId === face.id
          return (
            <group key={face.id} scale={selected ? 1.06 : 1}>
              {interactive && (
                <mesh
                  geometry={face.pick}
                  onClick={
                    onSelectPerspective
                      ? (event) => {
                          event.stopPropagation()
                          onSelectPerspective(face.id)
                        }
                      : undefined
                  }
                  onPointerOver={(event) => {
                    event.stopPropagation()
                    document.body.style.cursor = 'pointer'
                  }}
                  onPointerOut={() => {
                    document.body.style.cursor = 'auto'
                  }}
                >
                  <meshBasicMaterial transparent opacity={0} depthWrite={false} />
                </mesh>
              )}
              <mesh geometry={face.extrusion} raycast={() => null}>
                <meshStandardMaterial
                  color={face.color}
                  emissive={face.color}
                  emissiveIntensity={selected ? 1.55 : 0.38}
                  roughness={0.26}
                  metalness={0.14}
                  flatShading
                  toneMapped={false}
                />
              </mesh>
            </group>
          )
        })}
      </group>
    </group>
  )
}
