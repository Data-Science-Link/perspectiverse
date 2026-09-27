import { useEffect, useMemo } from 'react'
import { DoubleSide } from 'three'
import { spikeColor } from '../lib/colors'
import { createBodyTexture, createRingTexture } from '../lib/planetTextures'

const CORE_RADIUS = 0.32

const FACES = [
  { position: [0, CORE_RADIUS * 0.92, 0], rotation: [0, 0, 0] },
  { position: [0, -CORE_RADIUS * 0.92, 0], rotation: [Math.PI, 0, 0] },
  { position: [CORE_RADIUS * 0.92, 0, 0], rotation: [0, 0, -Math.PI / 2] },
  { position: [-CORE_RADIUS * 0.92, 0, 0], rotation: [0, 0, Math.PI / 2] },
  { position: [0, 0, CORE_RADIUS * 0.92], rotation: [Math.PI / 2, 0, 0] },
  { position: [0, 0, -CORE_RADIUS * 0.92], rotation: [-Math.PI / 2, 0, 0] },
]

function SaturnRings() {
  const texture = useMemo(() => createRingTexture(), [])
  useEffect(() => () => texture.dispose(), [texture])

  return (
    <mesh rotation={[Math.PI / 2.15, 0.18, 0]} raycast={() => null}>
      <ringGeometry args={[0.52, 1.08, 72]} />
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
  pickScale = 1,
  onSelectPerspective,
  interactive = true,
}) {
  const spikes = useMemo(
    () =>
      perspectives.slice(0, 6).map((perspective, index) => {
        const height = 0.16 + (perspective.volume_percent / 100) * 3.35
        return {
          ...perspective,
          index,
          height,
          color: spikeColor(index),
        }
      }),
    [perspectives],
  )

  const texture = useMemo(
    () => createBodyTexture(body?.key ?? 'mercury'),
    [body?.key],
  )

  useEffect(() => () => texture.dispose(), [texture])

  const color = body?.color ?? coreColor
  const emissive = dimmed ? 0.02 : body?.emissive ?? 0.35

  return (
    <group>
      <mesh>
        <sphereGeometry args={[CORE_RADIUS, 48, 32]} />
        <meshStandardMaterial
          map={texture}
          color={dimmed ? '#6b7280' : '#ffffff'}
          emissive={color}
          emissiveIntensity={emissive}
          roughness={body?.key === 'sun' ? 0.22 : 0.48}
          metalness={0.08}
          transparent
          opacity={dimmed ? 0.16 : 1}
        />
      </mesh>
      {body?.rings && !dimmed && <SaturnRings />}
      {spikes.map((spike) => {
        const selected = selectedPerspectiveId === spike.id
        const face = FACES[spike.index]
        return (
          <group key={spike.id} position={face.position} rotation={face.rotation}>
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
                <coneGeometry args={[0.46 * pickScale, spike.height * pickScale, 4]} />
                <meshBasicMaterial transparent opacity={0} depthWrite={false} />
              </mesh>
            )}
            <mesh
              position={[0, spike.height / 2, 0]}
              rotation={[0, Math.PI / 4, 0]}
              scale={selected ? 1.12 : 1}
              raycast={() => null}
            >
              <coneGeometry args={[0.28, spike.height, 4]} />
              <meshStandardMaterial
                color={spike.color}
                emissive={spike.color}
                emissiveIntensity={selected ? 1.6 : dimmed ? 0.02 : 0.32}
                roughness={0.28}
                metalness={0.12}
                transparent
                opacity={selected ? 1 : dimmed ? 0.12 : 1}
                flatShading
                toneMapped={false}
              />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}
