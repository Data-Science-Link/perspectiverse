import { useCallback, useEffect, useRef, useState } from 'react'
import { CameraControls, Stars } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { cameraOffsetForScale, topicScale } from '../lib/layout'
import { OrbitRing, default as Planet } from './Planet'

const HOME_VIEW_DESKTOP = [0, 6.2, 14.8, 0, 0, 0]
const HOME_VIEW_MOBILE = [0, 3.6, 10.6, 0, 0.15, 0]

function homeView(isMobile) {
  return isMobile ? HOME_VIEW_MOBILE : HOME_VIEW_DESKTOP
}
// camera-controls ACTION bits: ROTATE 1, TRUCK 2, DOLLY 16, TOUCH_ROTATE 64,
// TOUCH_TRUCK 128, TOUCH_DOLLY 1024, TOUCH_DOLLY_TRUCK 4096. NONE is 0.
const ORBIT_MOUSE = { left: 1, middle: 16, right: 2, wheel: 16 }
const INSPECT_MOUSE = { left: 0, middle: 0, right: 0, wheel: 16 }
const ORBIT_TOUCH = { one: 64, two: 4096, three: 128 }
const INSPECT_TOUCH = { one: 0, two: 1024, three: 0 }

function FocusCamera({ controlsRef, anchors, selectedTopic, isMobile }) {
  const lastId = useRef(null)

  useFrame(() => {
    const controls = controlsRef.current
    if (!controls) return

    if (!selectedTopic) {
      if (lastId.current !== null) {
        controls.setLookAt(...homeView(isMobile), true)
        lastId.current = null
      }
      return
    }

    if (lastId.current === selectedTopic.id) return
    const position = anchors.current[selectedTopic.id]
    if (!position) return

    const distance = cameraOffsetForScale(topicScale(selectedTopic.total_volume_percent))
    controls.setLookAt(
      position.x + distance,
      position.y + 1.35,
      position.z + distance,
      position.x,
      position.y,
      position.z,
      true,
    )
    lastId.current = selectedTopic.id
  })

  return null
}

function Universe({
  topics,
  selectedTopicId,
  selectedPerspectiveId,
  isMobile,
  onSelectTopic,
  onSelectPerspective,
}) {
  const controlsRef = useRef()
  const anchors = useRef({})
  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null
  const inspecting = Boolean(selectedTopic)

  useEffect(() => {
    return () => {
      document.body.style.cursor = 'auto'
    }
  }, [])

  return (
    <>
      <color attach="background" args={['#05060b']} />
      <fog attach="fog" args={['#05060b', 26, 72]} />
      <ambientLight intensity={0.46} />
      <pointLight position={[0, 0, 0]} intensity={2.4} distance={42} color="#ffe7a3" />
      <pointLight position={[12, 14, 8]} intensity={0.85} color="#9db7ff" />
      <directionalLight position={[-8, 10, 6]} intensity={0.55} color="#fff6d8" />
      <Stars radius={80} depth={50} count={6000} factor={4.2} saturation={0} fade speed={0.4} />
      {topics.slice(1).map((topic, index) => (
        <OrbitRing key={`ring-${topic.id}`} index={index + 1} />
      ))}
      {topics.map((topic, index) => (
        <Planet
          key={topic.id}
          topic={topic}
          index={index}
          selected={topic.id === selectedTopicId}
          dimmed={Boolean(selectedTopicId) && topic.id !== selectedTopicId}
          selectedPerspectiveId={topic.id === selectedTopicId ? selectedPerspectiveId : null}
          anchors={anchors}
          onSelectTopic={onSelectTopic}
          onSelectPerspective={onSelectPerspective}
          isMobile={isMobile}
        />
      ))}
      <CameraControls
        ref={controlsRef}
        makeDefault
        minDistance={3.2}
        maxDistance={46}
        dollyToCursor
        smoothTime={0.35}
        mouseButtons={inspecting ? INSPECT_MOUSE : ORBIT_MOUSE}
        touches={inspecting ? INSPECT_TOUCH : ORBIT_TOUCH}
      />
      <FocusCamera
        controlsRef={controlsRef}
        anchors={anchors}
        selectedTopic={selectedTopic}
        isMobile={isMobile}
      />
      <EffectComposer disableNormalPass>
        <Bloom intensity={0.32} luminanceThreshold={0.42} luminanceSmoothing={0.45} mipmapBlur />
      </EffectComposer>
    </>
  )
}

export default function Observatory({
  topics,
  selectedTopicId,
  selectedPerspectiveId,
  category,
  isMobile = false,
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
}) {
  const [epoch, setEpoch] = useState(0)
  const onCreated = useCallback(({ gl }) => {
    const canvas = gl.domElement
    let remounted = false
    const remount = () => {
      if (remounted) return
      remounted = true
      setEpoch((value) => value + 1)
    }
    const onLost = (event) => {
      event.preventDefault()
      remount()
    }
    canvas.addEventListener('webglcontextlost', onLost)
    canvas.addEventListener('webglcontextrestored', remount)
  }, [])

  const hint = selectedTopicId
    ? 'The crystal is the conversation · Drag to turn · Tap a face to inspect it'
    : 'Drag to orbit · Pinch or scroll to zoom · Tap a planet to dissolve it into geometry'

  return (
    <section className="observatory">
      <Canvas
        key={`${epoch}-${isMobile ? 'm' : 'd'}`}
        camera={{
          position: isMobile ? [0, 3.6, 10.6] : [0, 6.2, 14.8],
          fov: isMobile ? 48 : 42,
          near: 0.1,
          far: 120,
        }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: 'high-performance', failIfMajorPerformanceCaveat: false }}
        onPointerMissed={onClearSelection}
        onCreated={onCreated}
      >
        <Universe
          topics={topics}
          selectedTopicId={selectedTopicId}
          selectedPerspectiveId={selectedPerspectiveId}
          isMobile={isMobile}
          onSelectTopic={onSelectTopic}
          onSelectPerspective={onSelectPerspective}
        />
      </Canvas>
      {topics.length === 0 && (
        <div className="observatory-empty">
          <p>No planets in {category}.</p>
        </div>
      )}
      <div className="observatory-chrome">
        <p>{hint}</p>
      </div>
    </section>
  )
}
