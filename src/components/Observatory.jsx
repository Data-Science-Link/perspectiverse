import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CameraControls, Stars } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { cameraOffsetForScale, homeLookAt, homeMaxDistance, layoutSolarSystem, orbitElements, topicScale } from '../lib/layout'
import { solarSettings } from '../lib/solarSettings'
import { OrbitRing, default as Planet } from './Planet'
import TwinklingStars from './TwinklingStars'

function homeView(isMobile, planetCount = 10, layoutExtent = null) {
  return homeLookAt(isMobile, planetCount, layoutExtent)
}
// camera-controls ACTION bits: ROTATE 1, TRUCK 2, DOLLY 16, TOUCH_ROTATE 64,
// TOUCH_TRUCK 128, TOUCH_DOLLY 1024, TOUCH_DOLLY_TRUCK 4096. NONE is 0.
const ORBIT_MOUSE = { left: 1, middle: 16, right: 2, wheel: 16 }
const INSPECT_MOUSE = { left: 0, middle: 0, right: 0, wheel: 16 }
const ORBIT_TOUCH = { one: 64, two: 4096, three: 128 }
const INSPECT_TOUCH = { one: 0, two: 1024, three: 0 }

function FocusCamera({
  controlsRef,
  anchors,
  selectedTopic,
  isMobile,
  planetCount = 10,
  volumeMax = 100,
  layoutExtent = null,
}) {
  const lastId = useRef(null)
  const booted = useRef(false)

  useEffect(() => {
    booted.current = false
  }, [isMobile, planetCount, layoutExtent])

  useFrame(() => {
    const controls = controlsRef.current
    if (!controls) return
    const home = homeView(isMobile, planetCount, layoutExtent)

    if (!selectedTopic) {
      if (!booted.current || lastId.current !== null) {
        controls.setLookAt(...home, lastId.current !== null)
        lastId.current = null
        booted.current = true
      }
      return
    }

    if (lastId.current === selectedTopic.id) return
    const position = anchors.current[selectedTopic.id]
    if (!position) return

    const distance = cameraOffsetForScale(topicScale(selectedTopic.total_volume_percent, volumeMax))
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
    booted.current = true
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
  showOrbits = false,
  volumeMax = 100,
  layout = { radii: [], extent: null },
  settings,
}) {
  const controlsRef = useRef()
  const anchors = useRef({})
  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null
  const inspecting = Boolean(selectedTopic)
  const maxDistance = homeMaxDistance(isMobile, topics.length, layout.extent)

  useEffect(() => {
    return () => {
      document.body.style.cursor = 'auto'
    }
  }, [])

  return (
    <>
      <color attach="background" args={['#05060b']} />
      <fog attach="fog" args={['#05060b', 90, 170]} />
      <ambientLight intensity={0.28} />
      <pointLight position={[0, 0, 0]} intensity={2.8} distance={80} color="#ffe7a3" />
      <pointLight position={[12, 14, 8]} intensity={0.7} color="#9db7ff" />
      <directionalLight position={[-8, 10, 6]} intensity={1.15} color="#fff6d8" />
      {settings.dreiStars > 0 && (
        <Stars
          radius={120}
          depth={70}
          count={settings.dreiStars}
          factor={3.8}
          saturation={0}
          fade
          speed={0.18}
        />
      )}
      <TwinklingStars count={settings.twinkleStars} radius={110} />
      {showOrbits && topics.slice(1).map((topic, index) => {
        const orbit = orbitElements(index + 1, false, topic.id, layout.radii[index + 1])
        return (
          <OrbitRing
            key={`ring-${topic.id}`}
            radius={layout.radii[index + 1]}
            inclination={orbit.inclination}
            node={orbit.node}
            segments={settings.ringSegments}
          />
        )
      })}
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
          volumeMax={volumeMax}
          orbitRadius={layout.radii[index]}
          quality={settings.textureQuality}
          sphereDetail={settings.sphereDetail}
          haloDetail={settings.haloDetail}
        />
      ))}
      <CameraControls
        ref={controlsRef}
        makeDefault
        minDistance={3.2}
        maxDistance={maxDistance}
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
        planetCount={topics.length}
        volumeMax={volumeMax}
        layoutExtent={layout.extent}
      />
      {settings.bloom && !inspecting && (
        <EffectComposer disableNormalPass>
          <Bloom intensity={0.32} luminanceThreshold={0.42} luminanceSmoothing={0.45} mipmapBlur />
        </EffectComposer>
      )}
    </>
  )
}

export default function Observatory({
  topics,
  selectedTopicId,
  selectedPerspectiveId,
  category,
  isMobile = false,
  volumeMax = 100,
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
}) {
  const [epoch, setEpoch] = useState(0)
  const [showOrbits, setShowOrbits] = useState(false)
  const remounts = useRef(0)
  const settings = useMemo(() => solarSettings(isMobile), [isMobile])
  const layout = useMemo(() => layoutSolarSystem(topics, volumeMax), [topics, volumeMax])
  const home = useMemo(
    () => homeLookAt(isMobile, topics.length, layout.extent),
    [isMobile, topics.length, layout.extent],
  )
  const onCreated = useCallback(({ gl }) => {
    const canvas = gl.domElement
    const onLost = (event) => {
      event.preventDefault()
      if (remounts.current >= 1) return
      remounts.current += 1
      setEpoch((value) => value + 1)
    }
    canvas.addEventListener('webglcontextlost', onLost)
  }, [])

  const hint = 'Drag to look around'

  return (
    <section className="observatory">
      <Canvas
        key={`${epoch}-${isMobile ? 'm' : 'd'}`}
        camera={{
          position: [home[0], home[1], home[2]],
          fov: isMobile ? 48 : 42,
          near: 0.1,
          far: 180,
        }}
        dpr={settings.dpr}
        gl={{
          antialias: settings.antialias,
          powerPreference: settings.powerPreference,
          failIfMajorPerformanceCaveat: false,
          preserveDrawingBuffer: true,
          stencil: false,
        }}
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
          showOrbits={showOrbits}
          volumeMax={volumeMax}
          layout={layout}
          settings={settings}
        />
      </Canvas>
      {topics.length === 0 && (
        <div className="observatory-empty">
          <p>No planets in {category}.</p>
        </div>
      )}
      <div className="observatory-chrome">
        <p>{hint}</p>
        <button
          type="button"
          className={`orbit-toggle ${showOrbits ? 'is-on' : ''}`}
          aria-pressed={showOrbits}
          onClick={() => setShowOrbits((value) => !value)}
        >
          {showOrbits ? 'Hide orbit lines' : 'Show orbit lines'}
        </button>
      </div>
    </section>
  )
}
