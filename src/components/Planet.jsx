import { useRef } from 'react'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { hexToRgba, topicColor } from '../lib/colors'
import { orbitInclination, orbitRadius, orbitSpeed, topicScale } from '../lib/layout'
import SpikyCube from './SpikyCube'

export default function Planet({
  topic,
  index,
  selected,
  dimmed,
  selectedPerspectiveId,
  anchors,
  onSelectTopic,
  onSelectPerspective,
}) {
  const group = useRef()
  const cube = useRef()
  const angle = useRef(index * 0.62)
  const isSun = index === 0
  const radius = orbitRadius(index, isSun)
  const speed = orbitSpeed(index, isSun)
  const inclination = orbitInclination(index, isSun)
  const scale = topicScale(topic.total_volume_percent)
  const color = topicColor(topic.id)

  useFrame((_, delta) => {
    if (!isSun && !selected) {
      angle.current += delta * speed
    }

    if (group.current) {
      if (isSun) {
        group.current.position.set(0, 0, 0)
      } else {
        const t = angle.current
        group.current.position.set(
          Math.cos(t) * radius,
          Math.sin(t) * inclination * radius,
          Math.sin(t) * radius,
        )
      }
      if (anchors?.current) {
        anchors.current[topic.id] = group.current.position.clone()
      }
    }

    if (cube.current) {
      cube.current.rotation.x += delta * 0.22
      cube.current.rotation.y += delta * 0.34
      cube.current.rotation.z += delta * 0.08
    }
  })

  return (
    <group ref={group}>
      <group
        scale={scale}
        onClick={(event) => {
          event.stopPropagation()
          onSelectTopic(topic.id)
        }}
        onPointerOver={(event) => {
          event.stopPropagation()
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'auto'
        }}
      >
        {isSun && (
          <mesh>
            <sphereGeometry args={[1.15, 24, 24]} />
            <meshBasicMaterial color={color} transparent opacity={0.09} />
          </mesh>
        )}
        <group ref={cube}>
          <SpikyCube
            perspectives={topic.perspectives}
            coreColor={color}
            selectedPerspectiveId={selectedPerspectiveId}
            dimmed={dimmed}
            onSelectPerspective={(perspectiveId) => {
              onSelectTopic(topic.id)
              onSelectPerspective(perspectiveId)
            }}
          />
        </group>
      </group>
      <Html
        position={[0, scale * 1.35, 0]}
        center
        distanceFactor={18}
        style={{ pointerEvents: 'none' }}
      >
        <div
          className="planet-label"
          style={{
            opacity: dimmed ? 0.28 : 1,
            borderColor: hexToRgba(color, dimmed ? 0.18 : 0.55),
          }}
        >
          {topic.name}
        </div>
      </Html>
    </group>
  )
}

export function OrbitRing({ index }) {
  const radius = orbitRadius(index, false)
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} raycast={() => null}>
      <ringGeometry args={[radius - 0.01, radius + 0.01, 128]} />
      <meshBasicMaterial color="#9aa6d6" transparent opacity={0.07} />
    </mesh>
  )
}
