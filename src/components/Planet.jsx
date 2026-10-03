import { useEffect, useMemo, useRef, useState } from 'react'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { AdditiveBlending, CatmullRomCurve3, DoubleSide, Quaternion, TubeGeometry, Vector3 } from 'three'
import { hexToRgba, rankPerspectives, topicColor } from '../lib/colors'
import { faceLayout } from '../lib/faces'
import { bodySpin, formatPercent, orbitElements, setOrbitPosition, topicScale } from '../lib/layout'
import SpikyCube from './SpikyCube'

const _world = new Vector3()
const _toCamera = new Vector3()
const _look = new Vector3()
const _target = new Quaternion()
const _align = new Quaternion()
const _tilt = new Quaternion()
const _axisX = new Vector3(1, 0, 0)
const _axisY = new Vector3(0, 1, 0)

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
  volumeMax = 100,
  orbitRadius: orbitDistance = null,
  quality = 'high',
  sphereDetail = [48, 36],
  haloDetail = [32, 32],
}) {
  const group = useRef()
  const cube = useRef()
  const drag = useRef(null)
  const suppressClick = useRef(false)
  const [hovered, setHovered] = useState(false)
  const body = topic.body
  const isSun = body?.key === 'sun' || index === 0
  const orbit = useMemo(
    () => orbitElements(index, isSun, topic.id, orbitDistance),
    [index, isSun, topic.id, orbitDistance],
  )
  const spin = useMemo(() => bodySpin(topic.id, index), [topic.id, index])
  const spinAxis = useMemo(() => new Vector3(...spin.axis), [spin])
  const angle = useRef(orbit.phase)
  const scale = topicScale(topic.total_volume_percent, volumeMax)
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

    const aimIndex = focusIndex >= 0 ? focusIndex : 0
    if (selected && layout[aimIndex] && !drag.current) {
      group.current.getWorldPosition(_world)
      _toCamera.copy(state.camera.position).sub(_world).normalize()
      _look.set(...layout[aimIndex].direction)
      _align.setFromUnitVectors(_look, _toCamera)
      // A straight-on spike collapses into a diamond. Turn it so the point and the cube both read.
      _tilt.setFromAxisAngle(_axisY, 0.7)
      _target.copy(_tilt).multiply(_align)
      _tilt.setFromAxisAngle(_axisX, -0.28)
      _target.premultiply(_tilt)
      cube.current.quaternion.slerp(_target, 1 - Math.exp(-delta * 6))
      return
    }

    if (drag.current || selected) return
    cube.current.rotateOnAxis(spinAxis, delta * spin.speed)
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
    cube.current.rotateOnWorldAxis(_axisY, dx * 0.012)
    cube.current.rotateOnWorldAxis(_axisX, dy * 0.012)
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
        {isSun && !selected && !dimmed && (
          <group raycast={() => null}>
            <mesh raycast={() => null} renderOrder={1}>
              <sphereGeometry args={[1.08, haloDetail[0], haloDetail[1]]} />
              <meshBasicMaterial
                color="#ffe7a0"
                transparent
                opacity={0.28}
                blending={AdditiveBlending}
                depthWrite={false}
                depthTest
                toneMapped={false}
              />
            </mesh>
            <mesh raycast={() => null} renderOrder={1}>
              <sphereGeometry args={[1.28, Math.max(16, haloDetail[0] - 8), Math.max(16, haloDetail[1] - 8)]} />
              <meshBasicMaterial
                color={color}
                transparent
                opacity={0.14}
                blending={AdditiveBlending}
                depthWrite={false}
                depthTest
                toneMapped={false}
              />
            </mesh>
            <mesh raycast={() => null} renderOrder={1}>
              <sphereGeometry args={[1.52, Math.max(12, haloDetail[0] - 12), Math.max(12, haloDetail[1] - 12)]} />
              <meshBasicMaterial
                color="#ffb347"
                transparent
                opacity={0.07}
                blending={AdditiveBlending}
                depthWrite={false}
                depthTest
                toneMapped={false}
              />
            </mesh>
          </group>
        )}
        <group ref={cube}>
          <SpikyCube
            perspectives={topic.perspectives}
            body={body}
            coreColor={color}
            selectedPerspectiveId={selectedPerspectiveId}
            dimmed={dimmed}
            showSpikes={selected}
            showLabels={selected}
            quality={quality}
            sphereDetail={sphereDetail}
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

export function OrbitRing({ radius, inclination = 0, node = 0, segments = 128 }) {
  const geometry = useMemo(() => {
    if (!radius) return null
    const points = []
    const point = new Vector3()
    for (let index = 0; index < segments; index += 1) {
      setOrbitPosition(point, radius, (index / segments) * Math.PI * 2, inclination, node)
      points.push(point.clone())
    }
    const curve = new CatmullRomCurve3(points, true, 'chordal')
    return new TubeGeometry(curve, segments, 0.022, 8, true)
  }, [radius, inclination, node, segments])

  useEffect(() => () => geometry?.dispose(), [geometry])

  if (!geometry) return null
  return (
    <mesh geometry={geometry} raycast={() => null} renderOrder={-1}>
      <meshBasicMaterial
        color="#d7def5"
        transparent
        opacity={0.55}
        depthWrite={false}
        side={DoubleSide}
      />
    </mesh>
  )
}
