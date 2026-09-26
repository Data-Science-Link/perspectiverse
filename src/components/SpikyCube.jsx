import { useMemo } from 'react'
import { spikeColor } from '../lib/colors'

const BOX_SIZE = 0.72
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
  onSelectPerspective,
  interactive = true,
}) {
  const spikes = useMemo(
    () =>
      perspectives.slice(0, 6).map((perspective, index) => {
        const height = 0.22 + (perspective.volume_percent / 100) * 1.85
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
          emissiveIntensity={dimmed ? 0.08 : 0.28}
          roughness={0.38}
          metalness={0.22}
          transparent
          opacity={dimmed ? 0.35 : 1}
        />
      </mesh>
      {spikes.map((spike) => {
        const selected = selectedPerspectiveId === spike.id
        const face = FACES[spike.index]
        return (
          <group key={spike.id} position={face.position} rotation={face.rotation}>
            <mesh
              position={[0, spike.height / 2, 0]}
              rotation={[0, Math.PI / 4, 0]}
              onClick={
                interactive && onSelectPerspective
                  ? (event) => {
                      event.stopPropagation()
                      onSelectPerspective(spike.id)
                    }
                  : undefined
              }
              onPointerOver={
                interactive
                  ? (event) => {
                      event.stopPropagation()
                      document.body.style.cursor = 'pointer'
                    }
                  : undefined
              }
              onPointerOut={
                interactive
                  ? () => {
                      document.body.style.cursor = 'auto'
                    }
                  : undefined
              }
            >
              <coneGeometry args={[0.5, spike.height, 4]} />
              <meshStandardMaterial
                color={spike.color}
                emissive={spike.color}
                emissiveIntensity={selected ? 1.15 : dimmed ? 0.04 : 0.22}
                roughness={0.32}
                metalness={0.18}
                transparent
                opacity={dimmed ? 0.28 : 1}
              />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}
