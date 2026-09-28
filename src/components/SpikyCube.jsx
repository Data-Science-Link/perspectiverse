import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { BufferAttribute, BufferGeometry, DoubleSide } from 'three'
import { faceOpacity, rankPerspectives, shadeHex } from '../lib/colors'
import { CORE_RADIUS } from '../lib/faces'
import { createBodyTexture, createRingTexture } from '../lib/planetTextures'
import { cubeSpikeFaces, faceHeight, polyhedron } from '../lib/polyhedra'

function SaturnRings({ meshRef, quality = 'high' }) {
  const texture = useMemo(() => createRingTexture(quality), [quality])
  // Cached globally — do not dispose on unmount.

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

function fan(vertices) {
  const triangles = []
  for (let index = 1; index < vertices.length - 1; index += 1) {
    triangles.push([vertices[0], vertices[index], vertices[index + 1]])
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

function insetVertices(vertices, keep = 0.34) {
  const centroid = faceCentroid(vertices)
  return vertices.map((vertex) => centroid.clone().lerp(vertex, keep))
}

function buildCrystal(perspectives, pigment) {
  const ranked = rankPerspectives(perspectives)
  const loudest = ranked[0]?.volume_percent ?? 0
  const solid = polyhedron(6)
  const spikeFaces = cubeSpikeFaces(ranked.length)
  const coreTriangles = []
  for (const loop of solid.faces) {
    coreTriangles.push(...triangulate(solid.vertices, loop))
  }
  const faces = ranked.map((perspective, index) => {
    const loop = solid.faces[spikeFaces[index]]
    const verts = loop.map((vertexIndex) => solid.vertices[vertexIndex].clone())
    const normal = solid.normals[spikeFaces[index]].clone()
    const centroid = faceCentroid(verts)
    const height = faceHeight(perspective.volume_percent)
    const base = insetVertices(verts, 0.22).map((vertex) => vertex.addScaledVector(normal, 0.018))
    const pickBase = insetVertices(verts, 0.42).map((vertex) => vertex.addScaledVector(normal, 0.018))
    const apex = centroid.clone().addScaledVector(normal, height)
    const pickApex = centroid.clone().addScaledVector(normal, height * 1.18)
    const extrusion = [...fan(base)]
    const pick = [...fan(pickBase)]
    for (let edge = 0; edge < base.length; edge += 1) {
      const a = base[edge]
      const b = base[(edge + 1) % base.length]
      extrusion.push([a, b, apex])
    }
    for (let edge = 0; edge < pickBase.length; edge += 1) {
      const a = pickBase[edge]
      const b = pickBase[(edge + 1) % pickBase.length]
      pick.push([a, b, pickApex])
    }
    return {
      ...perspective,
      index,
      color: pigment,
      opacity: faceOpacity(perspective.volume_percent, loudest),
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
  quality = 'high',
  sphereDetail = [48, 36],
}) {
  const reveal = useRef(showSpikes ? 1 : 0)
  const sphereMat = useRef()
  const sphereMesh = useRef()
  const crystal = useRef()
  const ringMat = useRef()
  const ringMesh = useRef()
  const [crystalReady, setCrystalReady] = useState(showSpikes)
  const pigment = body?.color ?? coreColor

  const texture = useMemo(
    () => createBodyTexture(body?.key ?? 'mercury', quality),
    [body?.key, quality],
  )
  const crystalGeo = useMemo(
    () => (crystalReady ? buildCrystal(perspectives, pigment) : null),
    [crystalReady, perspectives, pigment],
  )

  useEffect(() => {
    if (showSpikes) setCrystalReady(true)
  }, [showSpikes])

  useEffect(() => () => {
    if (!crystalGeo) return
    crystalGeo.core.dispose()
    for (const face of crystalGeo.faces) {
      face.extrusion.dispose()
      face.pick.dispose()
    }
  }, [crystalGeo])

  useFrame((_, delta) => {
    const target = showSpikes && !dimmed ? 1 : 0
    reveal.current += (target - reveal.current) * Math.min(1, delta * 5.2)
    const amount = reveal.current
    if (sphereMat.current) {
      sphereMat.current.opacity = dimmed ? 0.16 : 1 - amount
      sphereMat.current.transparent = true
      sphereMat.current.depthWrite = amount < 0.55
    }
    if (sphereMesh.current) {
      sphereMesh.current.scale.setScalar(1 - amount * 0.05)
      sphereMesh.current.visible = amount < 0.97
    }
    if (crystal.current) {
      crystal.current.visible = amount > 0.02
      crystal.current.scale.setScalar(0.9 + amount * 0.1)
    }
    if (ringMat.current) {
      ringMat.current.opacity = (1 - amount) * 0.92
    }
    if (ringMesh.current) {
      ringMesh.current.visible = !dimmed && amount < 0.97
    }
  })

  const color = pigment
  const isSun = body?.key === 'sun'
  const emissive = dimmed ? 0.02 : isSun ? 1.15 : 0.035
  const emissiveColor = dimmed ? '#6b7280' : isSun ? color : '#fff4dc'
  const faces = crystalGeo
    ? [...crystalGeo.faces].sort((a, b) => b.opacity - a.opacity)
    : []

  return (
    <group>
      <mesh ref={sphereMesh}>
        <sphereGeometry args={[CORE_RADIUS, sphereDetail[0], sphereDetail[1]]} />
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
          quality={quality}
          meshRef={(node) => {
            ringMesh.current = node
            ringMat.current = node?.material ?? null
          }}
        />
      )}
      {crystalGeo && (
        <group ref={crystal}>
          <mesh geometry={crystalGeo.core} raycast={() => null}>
            <meshStandardMaterial
              color={shadeHex(pigment, 0.42)}
              emissive={pigment}
              emissiveIntensity={0.18}
              roughness={0.4}
              metalness={0.16}
              flatShading
            />
          </mesh>
          {faces.map((face) => {
            const selected = selectedPerspectiveId === face.id
            const transparent = face.opacity < 0.98
            return (
              <group key={face.id} scale={selected ? 1.05 : 1}>
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
                    emissiveIntensity={selected ? 1.15 : 0.16 + face.opacity * 0.28}
                    roughness={0.28}
                    metalness={0.1}
                    flatShading
                    toneMapped={false}
                    transparent={transparent}
                    opacity={face.opacity}
                    depthWrite={!transparent}
                    polygonOffset
                    polygonOffsetFactor={-1}
                    polygonOffsetUnits={-1}
                  />
                </mesh>
              </group>
            )
          })}
        </group>
      )}
    </group>
  )
}
