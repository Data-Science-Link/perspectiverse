import { useMemo, useRef, useState } from 'react'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { Quaternion, Vector3 } from 'three'
import { hexToRgba, rankPerspectives, topicColor } from '../lib/colors'
import { faceLayout } from '../lib/faces'
import { formatPercent, orbitElements, orbitRadius, setOrbitPosition, topicScale } from '../lib/layout'
import SpikyCube from './SpikyCube'

const _world = new Vector3()
const _toCamera = new Vector3()
const _look = new Vector3()
const _target = new Quaternion()

export default function Planet({
  topic,
  index,
  selected,
  dimmed,
  selectedPerspectiveId,
  anchors,
  onSelectTopic,
  onSelectPerspective,
  isMobile = false,
}) {
  const group = useRef()
  const cube = useRef()
  const drag = useRef(null)
  const suppressClick = useRef(false)
  const [hovered, setHovered] = useState(false)
  const body = topic.body
  const isSun = body?.key === 'sun' || index === 0
  const orbit = useMemo(
    () => orbitElements(index, isSun, topic.id),
    [index, isSun, topic.id],
  )
  const angle = useRef(orbit.phase)
  const scale = topicScale(topic.total_volume_percent)
  const color = topicColor(topic.id, body)
  const ranked = useMemo(
    () => rankPerspectives(topic.perspectives),
    [topic.perspectives],
  )
  const layout = useMemo(() => faceLayout(ranked.length), [ranked.length])
  const focusIndex = ranked.findIndex((face) => face.id === selectedPerspectiveId)

  useFrame((state, delta) => {
    if (!isSun && !selected) {
      angle.current += delta * orbit.speed
    }

    if (group.current) {
      if (isSun) {
        group.current.position.set(0, 0, 0)
      } else {
        setOrbitPosition(
          group.current.position,
          orbit.radius,
          angle.current,
          orbit.inclination,
          orbit.node,
        )
      }
      if (anchors?.current) {
        anchors.current[topic.id] = group.current.position.clone()
      }
    }

    if (!cube.current) return

    if (selected && focusIndex >= 0 && layout[focusIndex] && !drag.current) {
      group.current.getWorldPosition(_world)
      _toCamera.copy(state.camera.position).sub(_world).normalize()
      _look.set(...layout[focusIndex].direction)
      _target.setFromUnitVectors(_look, _toCamera)
      cube.current.quaternion.slerp(_target, 1 - Math.exp(-delta * 6))
      return
    }

    if (!selected) {
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
        {isSun && !selected && (
          <mesh raycast={() => null}>
            <sphereGeometry args={[1.08, 32, 32]} />
            <meshBasicMaterial color={color} transparent opacity={0.16} />
          </mesh>
        )}
        <group ref={cube}>
          <SpikyCube
            perspectives={topic.perspectives}
            body={body}
            coreColor={color}
            selectedPerspectiveId={selectedPerspectiveId}
            dimmed={dimmed}
            showSpikes={selected}
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
      <Html
        position={[0, scale * (isMobile ? 1.32 : 1.45), 0]}
        center
        distanceFactor={isMobile ? 16 : 18}
        zIndexRange={[10, 0]}
        style={{ pointerEvents: 'none' }}
      >
        <button
          type="button"
          className={`planet-label ${dimmed ? 'is-dimmed' : ''} ${isMobile ? 'is-mobile' : ''}`}
          style={{
            borderColor: hexToRgba(color, dimmed ? 0.12 : 0.55),
            pointerEvents: 'auto',
          }}
          onClick={(event) => {
            event.stopPropagation()
            onSelectTopic(topic.id)
          }}
        >
          {topic.name}
        </button>
      </Html>
      {!isMobile && hovered && (
        <Html position={[0, scale * 1.95, 0]} center distanceFactor={20} zIndexRange={[12, 0]}>
          <div className="planet-hover">
            {topic.category} · {formatPercent(topic.total_volume_percent)}
          </div>
        </Html>
      )}
    </group>
  )
}

export function OrbitRing({ index, inclination = 0, node = 0 }) {
  const radius = orbitRadius(index, false)
  return (
    <group rotation={[0, node, 0]}>
      <mesh rotation={[Math.PI / 2 + inclination, 0, 0]} raycast={() => null}>
        <ringGeometry args={[radius - 0.016, radius + 0.016, 160]} />
        <meshBasicMaterial color="#d7def5" transparent opacity={0.34} />
      </mesh>
    </group>
  )
}
