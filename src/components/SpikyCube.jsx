import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { DoubleSide } from 'three'
import { spikeColor } from '../lib/colors'
import { CORE_RADIUS, faceLayout } from '../lib/faces'
import { createBodyTexture, createRingTexture } from '../lib/planetTextures'

function SaturnRings() {
  const texture = useMemo(() => createRingTexture(), [])
  useEffect(() => () => texture.dispose(), [texture])

  return (
    <mesh rotation={[Math.PI / 2.15, 0.18, 0]} raycast={() => null}>
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

export default function SpikyCube({
  perspectives = [],
  body = null,
  coreColor = '#f4c14e',
  selectedPerspectiveId = null,
  dimmed = false,
  showSpikes = true,
  pickScale = 1,
  onSelectPerspective,
  interactive = true,
}) {
  const reveal = useRef(showSpikes ? 1 : 0)
  const spikeGroup = useRef()
  const layout = useMemo(() => faceLayout(perspectives.length), [perspectives.length])
  const spikes = useMemo(
    () =>
      perspectives.slice(0, layout.length).map((perspective, index) => {
        const height = 0.28 + (perspective.volume_percent / 100) * 1.35
        return {
          ...perspective,
          index,
          height,
          color: spikeColor(index),
          face: layout[index],
        }
      }),
    [perspectives, layout],
  )

  const texture = useMemo(
    () => createBodyTexture(body?.key ?? 'mercury'),
    [body?.key],
  )

  useEffect(() => () => texture.dispose(), [texture])

  useFrame((_, delta) => {
    const target = showSpikes && !dimmed ? 1 : 0
    reveal.current += (target - reveal.current) * Math.min(1, delta * 8)
    if (spikeGroup.current) {
      const amount = reveal.current
      spikeGroup.current.visible = amount > 0.02
      spikeGroup.current.scale.setScalar(amount)
    }
  })

  const color = body?.color ?? coreColor
  const isSun = body?.key === 'sun'
  const emissive = dimmed ? 0.02 : isSun ? 1.15 : 0.06

  return (
    <group>
      <mesh>
        <sphereGeometry args={[CORE_RADIUS, 64, 48]} />
        <meshStandardMaterial
          map={texture}
          color={dimmed ? '#6b7280' : '#ffffff'}
          emissive={color}
          emissiveIntensity={emissive}
          roughness={isSun ? 0.28 : 0.62}
          metalness={0.04}
          transparent
          opacity={dimmed ? 0.16 : 1}
        />
      </mesh>
      {body?.rings && !dimmed && <SaturnRings />}
      <group ref={spikeGroup}>
        {spikes.map((spike) => {
          const selected = selectedPerspectiveId === spike.id
          const segments = spike.face.radialSegments
          return (
            <group
              key={spike.id}
              position={spike.face.position}
              quaternion={spike.face.quaternion}
            >
              {interactive && (
                <mesh
                  position={[0, (spike.height * pickScale) / 2, 0]}
                  rotation={[0, Math.PI / 4, 0]}
                  onClick={
                    onSelectPerspective
                      ? (event) => {
                          event.stopPropagation()
                          onSelectPerspective(spike.id)
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
                  <coneGeometry args={[0.5 * pickScale, spike.height * pickScale, segments]} />
                  <meshBasicMaterial transparent opacity={0} depthWrite={false} />
                </mesh>
              )}
              <mesh
                position={[0, spike.height / 2, 0]}
                rotation={[0, Math.PI / 4, 0]}
                scale={selected ? 1.12 : 1}
                raycast={() => null}
              >
                <coneGeometry args={[0.3, spike.height, segments]} />
                <meshStandardMaterial
                  color={spike.color}
                  emissive={spike.color}
                  emissiveIntensity={selected ? 1.6 : 0.32}
                  roughness={0.28}
                  metalness={0.12}
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
