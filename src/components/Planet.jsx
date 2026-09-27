import { useRef, useState } from 'react'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { hexToRgba, topicColor } from '../lib/colors'
import { formatPercent, orbitInclination, orbitRadius, orbitSpeed, topicScale } from '../lib/layout'
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
  const drag = useRef(null)
  const suppressClick = useRef(false)
  const [hovered, setHovered] = useState(false)
  const body = topic.body
  const isSun = body?.key === 'sun' || index === 0
  const radius = orbitRadius(index, isSun)
  const speed = orbitSpeed(index, isSun)
  const inclination = orbitInclination(index, isSun)
  const scale = topicScale(topic.total_volume_percent)
  const color = topicColor(topic.id, body)
  const pickScale = Math.max(1, 1.15 / Math.max(scale, 0.35))

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

    if (cube.current && !selected) {
      cube.current.rotation.x += delta * 0.22
      cube.current.rotation.y += delta * 0.34
      cube.current.rotation.z += delta * 0.08
    }
  })

  const startDrag = (event) => {
    if (!selected) return
    event.stopPropagation()
    suppressClick.current = false
    drag.current = { x: event.clientX, y: event.clientY, moved: false }
    if (event.target?.setPointerCapture && event.pointerId != null) {
      event.target.setPointerCapture(event.pointerId)
    }
  }

  const moveDrag = (event) => {
    if (!drag.current || !cube.current) return
    const dx = event.clientX - drag.current.x
    const dy = event.clientY - drag.current.y
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.current.moved = true
    cube.current.rotation.y += dx * 0.012
    cube.current.rotation.x += dy * 0.012
    drag.current.x = event.clientX
    drag.current.y = event.clientY
  }

  const endDrag = () => {
    if (drag.current?.moved) suppressClick.current = true
    drag.current = null
  }

  return (
    <group ref={group}>
      <group
        scale={scale}
        onClick={(event) => {
          event.stopPropagation()
          if (suppressClick.current) {
            suppressClick.current = false
            return
          }
          onSelectTopic(topic.id)
        }}
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerOver={(event) => {
          event.stopPropagation()
          setHovered(true)
          document.body.style.cursor = selected ? 'grab' : 'pointer'
        }}
        onPointerOut={() => {
          setHovered(false)
          document.body.style.cursor = 'auto'
        }}
      >
        <mesh>
          <sphereGeometry args={[0.95, 12, 12]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
        {isSun && (
          <mesh raycast={() => null}>
            <sphereGeometry args={[1.25, 24, 24]} />
            <meshBasicMaterial color={color} transparent opacity={0.14} />
          </mesh>
        )}
        <group ref={cube}>
          <SpikyCube
            perspectives={topic.perspectives}
            body={body}
            coreColor={color}
            selectedPerspectiveId={selectedPerspectiveId}
            dimmed={dimmed}
            pickScale={pickScale}
            onSelectPerspective={(perspectiveId) => {
              if (suppressClick.current) {
                suppressClick.current = false
                return
              }
              onSelectTopic(topic.id)
              onSelectPerspective(perspectiveId)
            }}
          />
        </group>
      </group>
      <Html position={[0, scale * 1.45, 0]} center distanceFactor={16} zIndexRange={[10, 0]}>
        <button
          type="button"
          className={`planet-label ${dimmed ? 'is-dimmed' : ''}`}
          style={{
            borderColor: hexToRgba(color, dimmed ? 0.12 : 0.55),
          }}
          onClick={(event) => {
            event.stopPropagation()
            onSelectTopic(topic.id)
          }}
        >
          {topic.name}
        </button>
      </Html>
      {hovered && (
        <Html position={[0, scale * 1.95, 0]} center distanceFactor={18} zIndexRange={[12, 0]}>
          <div className="planet-hover">
            {topic.category} · {formatPercent(topic.total_volume_percent)}
          </div>
        </Html>
      )}
    </group>
  )
}

export function OrbitRing({ index }) {
  const radius = orbitRadius(index, false)
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} raycast={() => null}>
      <ringGeometry args={[radius - 0.014, radius + 0.014, 160]} />
      <meshBasicMaterial color="#d7def5" transparent opacity={0.28} />
    </mesh>
  )
}
