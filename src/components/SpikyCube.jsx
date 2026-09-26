import { useMemo } from 'react'
import { spikeColor } from '../lib/colors'

const BOX_SIZE = 0.36
const BOX_HALF = BOX_SIZE / 2

const FACES = [
  { position: [0, BOX_HALF, 0], rotation: [0, 0, 0] },
  { position: [0, -BOX_HALF, 0], rotation: [Math.PI, 0, 0] },
  { position: [BOX_HALF, 0, 0], rotation: [0, 0, -Math.PI / 2] },
  { position: [-BOX_HALF, 0, 0], rotation: [0, 0, Math.PI / 2] },
  { position: [0, 0, BOX_HALF], rotation: [Math.PI / 2, 0, 0] },
  { position: [0, 0, -BOX_HALF], rotation: [-Math.PI / 2, 0, 0] },
]

export default function SpikyCube({
  perspectives = [],
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

  return (
    <group>
      <mesh>
        <boxGeometry args={[BOX_SIZE, BOX_SIZE, BOX_SIZE]} />
        <meshStandardMaterial
          color={coreColor}
          emissive={coreColor}
          emissiveIntensity={dimmed ? 0.02 : 0.45}
          roughness={0.34}
          metalness={0.16}
          transparent
          opacity={dimmed ? 0.12 : 1}
          flatShading
        />
      </mesh>
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
