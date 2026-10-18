import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { CameraControls, Stars } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { cameraOffsetForScale, homeLookAt, homeMaxDistance, layoutLinear, layoutSolarSystem, orbitElements, topicScale } from '../lib/layout'
import {
  clearSolarView,
  installSolarCameraTestHooks,
  restoreSolarView,
  solarLayoutKey,
  stashSolarView,
} from '../lib/solarCamera'
import TopicFilter from './TopicFilter'
import { solarSettings } from '../lib/solarSettings'
import { OrbitRing, default as Planet } from './Planet'
import TwinklingStars from './TwinklingStars'

function homeView(isMobile, planetCount = 10, layoutExtent = null, homeFrame = {}) {
  return homeLookAt(isMobile, planetCount, layoutExtent, homeFrame)
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
  homeFrame = {},
  layoutKey,
  limits,
}) {
  const lastId = useRef(null)
  const booted = useRef(false)

  useEffect(() => {
    booted.current = false
  }, [isMobile, planetCount, layoutExtent, homeFrame, layoutKey])

  useFrame(() => {
    const controls = controlsRef.current
    if (!controls) return
    const home = homeView(isMobile, planetCount, layoutExtent, homeFrame)

    if (!selectedTopic) {
      if (lastId.current !== null) {
        if (!restoreSolarView(controls, layoutKey, limits, true)) {
          controls.setLookAt(...home, true)
        }
        lastId.current = null
        booted.current = true
        return
      }
      if (!booted.current) {
        if (!restoreSolarView(controls, layoutKey, limits, false)) {
          controls.setLookAt(...home, false)
        }
        booted.current = true
      }
      return
    }

    if (lastId.current === selectedTopic.id) return
    const position = anchors.current[selectedTopic.id]
    if (!position) return

    if (lastId.current === null) {
      stashSolarView(controls, layoutKey)
    }

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
  layout = { radii: [], extent: null, positions: null },
  linear = false,
  labelDistanceFactor = 18,
  homeFrame = {},
  layoutKey,
  limits,
  settings,
}) {
  const controlsRef = useRef()
  const anchors = useRef({})
  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null
  const inspecting = Boolean(selectedTopic)
  const maxDistance = limits?.maxDistance ?? homeMaxDistance(isMobile, topics.length, layout.extent, homeFrame)

  const handleSelectTopic = useCallback(
    (topicId) => {
      if (selectedTopicId == null) {
        stashSolarView(controlsRef.current, layoutKey)
      }
      onSelectTopic(topicId)
    },
    [onSelectTopic, selectedTopicId, layoutKey],
  )

  useEffect(() => {
    installSolarCameraTestHooks(() => controlsRef.current, () => ({ layoutKey, limits }))
    return () => {
      document.body.style.cursor = 'auto'
      if (typeof window !== 'undefined' && window.__PV_SOLAR_CAMERA__) {
        delete window.__PV_SOLAR_CAMERA__
      }
    }
  }, [layoutKey, limits])

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
      {showOrbits && !linear && topics.slice(1).map((topic, index) => {
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
          onSelectTopic={handleSelectTopic}
          onSelectPerspective={onSelectPerspective}
          isMobile={isMobile}
          volumeMax={volumeMax}
          orbitRadius={linear ? null : layout.radii[index]}
          anchor={linear ? layout.positions[index] : null}
          labelDistanceFactor={linear ? labelDistanceFactor : undefined}
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
        homeFrame={homeFrame}
        layoutKey={layoutKey}
        limits={limits}
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
  categories = [],
  counts = {},
  isMobile = false,
  volumeMax = 100,
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
  onCategory,
}) {
  const [epoch, setEpoch] = useState(0)
  const [showOrbits, setShowOrbits] = useState(false)
  const [linear, setLinear] = useState(false)
  const [canvasAspect, setCanvasAspect] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth / window.innerHeight : 1.2,
  )
  const remounts = useRef(0)
  const prevLayoutKey = useRef(null)
  const aspectObserver = useRef(null)
  const settings = useMemo(() => solarSettings(isMobile), [isMobile])

  const bindCanvas = useCallback((canvas) => {
    if (!canvas || typeof ResizeObserver === 'undefined') return
    const measure = () => {
      const rect = canvas.getBoundingClientRect()
      if (rect.width > 0 && rect.height > 0) {
        setCanvasAspect(rect.width / rect.height)
      }
    }
    measure()
    aspectObserver.current?.disconnect()
    aspectObserver.current = new ResizeObserver(measure)
    aspectObserver.current.observe(canvas)
  }, [])

  useEffect(() => () => aspectObserver.current?.disconnect(), [])

  const layout = useMemo(
    () => (
      linear
        ? layoutLinear(topics, volumeMax, { grid: isMobile, viewportAspect: canvasAspect })
        : layoutSolarSystem(topics, volumeMax)
    ),
    [linear, topics, volumeMax, isMobile, canvasAspect],
  )
  const linearGrid = linear && layout.mode === 'grid'
  const homeFrame = useMemo(
    () => ({
      linear,
      grid: linearGrid,
      viewportAspect: canvasAspect,
      extentX: layout.extentX ?? layout.extent,
      extentY: layout.extentY ?? layout.extent,
    }),
    [linear, linearGrid, canvasAspect, layout.extent, layout.extentX, layout.extentY],
  )
  const home = useMemo(
    () => homeLookAt(isMobile, topics.length, layout.extent, homeFrame),
    [isMobile, topics.length, layout.extent, homeFrame],
  )
  const layoutKey = useMemo(
    () => solarLayoutKey(category, linear, linearGrid),
    [category, linear, linearGrid],
  )
  const limits = useMemo(
    () => ({
      minDistance: 3.2,
      maxDistance: homeMaxDistance(isMobile, topics.length, layout.extent, homeFrame),
      home,
      extent: layout.extent ?? 12,
      linear,
      grid: linearGrid,
    }),
    [isMobile, topics.length, layout.extent, linear, linearGrid, home, homeFrame],
  )
  const labelDistanceFactor = useMemo(() => {
    if (!linear) return isMobile ? 16 : 18
    if (isMobile) {
      const homeDistance = Math.hypot(home[0], home[1], home[2])
      return Math.min(30, Math.max(18, homeDistance * 1.15))
    }
    return 18
  }, [linear, isMobile, home])

  useLayoutEffect(() => {
    if (prevLayoutKey.current != null && prevLayoutKey.current !== layoutKey) {
      clearSolarView()
    }
    prevLayoutKey.current = layoutKey
  }, [layoutKey])

  useEffect(() => {
    if (!linear || typeof window === 'undefined') {
      delete window.__perspectiverseLinearLayout
      return undefined
    }
    window.__perspectiverseLinearLayout = {
      mode: layout.mode,
      cols: layout.cols ?? topics.length,
      positions: layout.positions,
    }
    return () => {
      delete window.__perspectiverseLinearLayout
    }
  }, [linear, layout, topics.length])

  const onCreated = useCallback(({ gl }) => {
    const canvas = gl.domElement
    bindCanvas(canvas)
    const onLost = (event) => {
      event.preventDefault()
      if (remounts.current >= 1) return
      remounts.current += 1
      setEpoch((value) => value + 1)
    }
    canvas.addEventListener('webglcontextlost', onLost)
  }, [bindCanvas])

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
          linear={linear}
          labelDistanceFactor={labelDistanceFactor}
          homeFrame={homeFrame}
          layoutKey={layoutKey}
          limits={limits}
          settings={settings}
        />
      </Canvas>
      {topics.length === 0 && (
        <div className="observatory-empty">
          <p>No planets in {category}.</p>
        </div>
      )}
      <div className="observatory-chrome">
        {onCategory && (
          <TopicFilter
            id="solar-topic-filter"
            categories={categories}
            category={category}
            counts={counts}
            onCategory={onCategory}
          />
        )}
        <div className="observatory-chrome-row">
          <p>{linear ? 'Largest to smallest' : hint}</p>
          <div className="observatory-actions">
            <button
              type="button"
              className={`orbit-toggle ${linear ? 'is-on' : ''}`}
              aria-pressed={linear}
              onClick={() => setLinear((value) => !value)}
            >
              {linear ? 'Orbits' : 'Linear'}
            </button>
            <button
              type="button"
              className={`orbit-toggle ${showOrbits ? 'is-on' : ''}`}
              aria-pressed={showOrbits}
              disabled={linear}
              onClick={() => setShowOrbits((value) => !value)}
            >
              {showOrbits ? 'Hide orbit lines' : 'Show orbit lines'}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
