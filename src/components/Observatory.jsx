import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { CameraControls, Stars } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { Vector3 } from 'three'
import { hexToRgba, topicColor } from '../lib/colors'
import { cameraOffsetForScale, homeLookAt, homeMaxDistance, layoutLinear, layoutSolarSystem, orbitElements, splitLabelLines, topicScale } from '../lib/layout'
import { separateLabelBoxes } from '../lib/orbitLabels'
import {
  clearSolarView,
  installSolarCameraTestHooks,
  mobileOrbitHome,
  orbitSamplePoints,
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

function estimateOrbitFrame(aspect) {
  const width = typeof window !== 'undefined' ? window.innerWidth : 390
  const height = typeof window !== 'undefined' ? window.innerHeight : 844
  const header = aspect > 1.15 ? 58 : 68
  const chrome = 120
  const canvasHeight = Math.max(80, height - header)
  return {
    width,
    height: canvasHeight,
    usable: {
      x: 8,
      y: 8,
      width: Math.max(40, width - 16),
      height: Math.max(40, canvasHeight - chrome - 8),
    },
  }
}

function measureOrbitFrame() {
  const canvas = document.querySelector('.observatory canvas')
  if (!canvas) return null
  const canvasRect = canvas.getBoundingClientRect()
  if (canvasRect.width < 40 || canvasRect.height < 40) return null
  const chrome = document.querySelector('.observatory-chrome')
  const chromeTop = chrome ? chrome.getBoundingClientRect().top : canvasRect.bottom
  const top = 8
  const bottom = Math.min(canvasRect.height - 8, chromeTop - canvasRect.top - 8)
  return {
    width: canvasRect.width,
    height: canvasRect.height,
    usable: {
      x: 8,
      y: top,
      width: Math.max(40, canvasRect.width - 16),
      height: Math.max(40, bottom - top),
    },
  }
}

function sameOrbitFrame(prev, next) {
  if (!prev || !next) return false
  const fields = [
    [prev.width, next.width],
    [prev.height, next.height],
    [prev.usable.x, next.usable.x],
    [prev.usable.y, next.usable.y],
    [prev.usable.width, next.usable.width],
    [prev.usable.height, next.usable.height],
  ]
  return fields.every(([left, right]) => Math.abs(left - right) < 1)
}

function estimatePhoneChrome(aspect) {
  const width = typeof window !== 'undefined' ? window.innerWidth : 390
  const height = typeof window !== 'undefined' ? window.innerHeight : 844
  const landscape = aspect > 1.15
  const filterBlock = landscape ? 136 : 156
  const top = 8
  return {
    viewport: { width, height },
    usable: {
      x: 6,
      y: top,
      width: Math.max(40, width - 12),
      height: Math.max(40, height - filterBlock - top),
    },
  }
}

const FILTER_LABEL_CLEARANCE = 12

function filterChromeTop(canvasRect) {
  const label = document.querySelector('.observatory .topic-filter span')
  if (label) return label.getBoundingClientRect().top
  const filter = document.getElementById('solar-topic-filter')
  if (filter) return filter.getBoundingClientRect().top
  return canvasRect.bottom
}

function measurePhoneChrome() {
  const canvas = document.querySelector('.observatory canvas')
  if (!canvas) return null
  const canvasRect = canvas.getBoundingClientRect()
  if (canvasRect.width < 20 || canvasRect.height < 20) return null
  const header = document.querySelector('header')
  const headerBottom = header ? header.getBoundingClientRect().bottom : canvasRect.top
  const filterTop = filterChromeTop(canvasRect)
  const top = Math.max(6, headerBottom - canvasRect.top + 4)
  const limit = Math.min(canvasRect.height - 6, filterTop - canvasRect.top - FILTER_LABEL_CLEARANCE)
  return {
    viewport: { width: canvasRect.width, height: canvasRect.height },
    usable: {
      x: 6,
      y: top,
      width: Math.max(40, canvasRect.width - 12),
      height: Math.max(40, limit - top),
    },
  }
}

function GridLabelText({ name, landscape }) {
  if (!landscape) return name
  return splitLabelLines(name).map((line, index) => (
    <span key={`${index}-${line}`} className="planet-label-line">{line}</span>
  ))
}

function gridLabelStyle(aspect, pillMaxWidth) {
  if (aspect > 1.15) {
    return {
      fontSize: '14px',
      lineHeight: 1.2,
      letterSpacing: '0.01em',
      width: 'max-content',
      maxWidth: 'none',
    }
  }
  return {
    width: pillMaxWidth ? `${pillMaxWidth}px` : undefined,
    maxWidth: pillMaxWidth ? `${pillMaxWidth}px` : undefined,
  }
}

function pillsChanged(prev, next) {
  if (!prev || prev.length !== next.length) return true
  return next.some((pill, index) => {
    const prior = prev[index]
    return Math.abs(prior.width - pill.width) > 0.5
      || Math.abs(prior.height - pill.height) > 0.5
      || prior.lines !== pill.lines
  })
}
// camera-controls ACTION bits: ROTATE 1, TRUCK 2, DOLLY 16, TOUCH_ROTATE 64,
// TOUCH_TRUCK 128, TOUCH_DOLLY 1024, TOUCH_DOLLY_TRUCK 4096. NONE is 0.
const ORBIT_MOUSE = { left: 1, middle: 16, right: 2, wheel: 16 }
const INSPECT_MOUSE = { left: 0, middle: 0, right: 0, wheel: 16 }
const ORBIT_TOUCH = { one: 64, two: 4096, three: 128 }
const INSPECT_TOUCH = { one: 0, two: 1024, three: 0 }

const _labelPoint = new Vector3()
const LABEL_HOLD_MS = 220

function OrbitLabelPlacer({ enabled, topics, anchors, layout, fitKey }) {
  const nudges = useRef(null)
  const nudgeKey = useRef('')

  useFrame(({ camera, gl }) => {
    if (!enabled) return
    const overlay = document.querySelector('.orbit-labels')
    if (!overlay) return
    const nodes = [...overlay.querySelectorAll('.planet-label')]
    if (nodes.length !== topics.length) return
    const canvasRect = gl.domElement.getBoundingClientRect()
    const overlayRect = overlay.getBoundingClientRect()
    if (canvasRect.width < 20 || canvasRect.height < 20) return

    const bases = []
    for (let index = 0; index < topics.length; index += 1) {
      const pos = anchors.current[topics[index].id]
      if (!pos) return
      const lift = (layout.items?.[index]?.scale ?? 1) * 1.32
      _labelPoint.set(pos.x, pos.y + lift, pos.z).project(camera)
      if (_labelPoint.z < -1 || _labelPoint.z > 1) return
      bases.push({
        x: (_labelPoint.x * 0.5 + 0.5) * canvasRect.width + (canvasRect.left - overlayRect.left),
        y: (1 - _labelPoint.y) * 0.5 * canvasRect.height + (canvasRect.top - overlayRect.top),
      })
    }

    const home = fitKey.split(',').map(Number)
    if (home.length >= 6) {
      const dx = camera.position.x - home[0]
      const dy = camera.position.y - home[1]
      const dz = camera.position.z - home[2]
      _labelPoint.set(home[3], home[4], home[5]).project(camera)
      const aimed = dx * dx + dy * dy + dz * dz < 0.64
        && Math.abs(_labelPoint.x) < 0.08
        && Math.abs(_labelPoint.y) < 0.08
        && _labelPoint.z < 1
      if (!aimed) return
    }
    if (nodes.some((node) => node.offsetWidth < 2)) return
    const header = document.querySelector('header')?.getBoundingClientRect()
    const chrome = document.querySelector('.observatory-chrome')?.getBoundingClientRect()
    const bounds = {
      left: 4,
      top: Math.max(4, (header ? header.bottom - overlayRect.top : 0) + 4),
      right: Math.max(40, overlayRect.width - 4),
      bottom: Math.max(40, (chrome ? chrome.top - overlayRect.top : overlayRect.height) - 4),
    }
    if (!(bounds.bottom > bounds.top + 24) || !(bounds.right > bounds.left + 24)) return
    const boxes = nodes.map((node, index) => ({
      x: bases[index].x - node.offsetWidth / 2,
      y: bases[index].y - node.offsetHeight / 2,
      w: node.offsetWidth,
      h: node.offsetHeight,
    }))
    const signature = `${fitKey}|${boxes.map((box) => `${Math.round(box.x)},${Math.round(box.y)},${box.w},${box.h}`).join(';')}`
    if (nudgeKey.current !== signature || !nudges.current) {
      nudges.current = separateLabelBoxes(boxes, bounds)
      nudgeKey.current = signature
    }

    let overlapping = nodes.some((node) => node._orbitLeft == null)
    if (!overlapping) {
      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i]
          const b = nodes[j]
          const ax = a._orbitLeft
          const ay = a._orbitTop
          const bx = b._orbitLeft
          const by = b._orbitTop
          const overlapX = Math.min(ax + a.offsetWidth, bx + b.offsetWidth) - Math.max(ax, bx)
          const overlapY = Math.min(ay + a.offsetHeight, by + b.offsetHeight) - Math.max(ay, by)
          if (overlapX > 0 && overlapY > 0) overlapping = true
        }
      }
    }

    const now = performance.now()
    nodes.forEach((node, index) => {
      const nudge = nudges.current[index] || { x: 0, y: 0 }
      const left = Math.round(boxes[index].x) + nudge.x
      const top = Math.round(boxes[index].y) + nudge.y
      if (node._orbitLeft === left && node._orbitTop === top) return
      if (node._orbitLeft != null && !overlapping && now < (node._orbitHold || 0)) return
      node._orbitLeft = left
      node._orbitTop = top
      node._orbitHold = now + LABEL_HOLD_MS
      node.style.left = `${left}px`
      node.style.top = `${top}px`
      node.style.visibility = 'visible'
    })
  })

  return null
}

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
  fitKey = '',
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
      <fog attach="fog" args={linear && layout.mode === 'grid' ? ['#05060b', 280, 640] : ['#05060b', 90, 170]} />
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
          labelDistanceFactor={labelDistanceFactor}
          planetVisualScale={linear ? (layout.planetVisualScale ?? 1) : 1}
          meshScale={linear && layout.meshScales ? layout.meshScales[index] : null}
          linearGrid={linear && layout.mode === 'grid'}
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
      {isMobile && !linear && (
        <OrbitLabelPlacer
          enabled
          topics={topics}
          anchors={anchors}
          layout={layout}
          fitKey={fitKey}
        />
      )}
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
  const [gridChrome, setGridChrome] = useState(null)
  const [gridPills, setGridPills] = useState(null)
  const [orbitFrame, setOrbitFrame] = useState(null)
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
    () => {
      if (!linear) return layoutSolarSystem(topics, volumeMax)
      const screen = isMobile ? (gridChrome ?? estimatePhoneChrome(canvasAspect)) : null
      return layoutLinear(topics, volumeMax, {
        grid: isMobile,
        viewportAspect: canvasAspect,
        screen: screen ? { ...screen, pills: gridPills } : null,
      })
    },
    [linear, topics, volumeMax, isMobile, canvasAspect, gridChrome, gridPills],
  )
  const linearGrid = linear && layout.mode === 'grid'

  useLayoutEffect(() => {
    if (linear || !isMobile) {
      setOrbitFrame(null)
      return undefined
    }
    const measure = () => {
      const next = measureOrbitFrame()
      if (!next) return
      setOrbitFrame((prev) => (sameOrbitFrame(prev, next) ? prev : next))
    }
    measure()
    const observer = new ResizeObserver(measure)
    const canvas = document.querySelector('.observatory canvas')
    const chrome = document.querySelector('.observatory-chrome')
    const header = document.querySelector('header')
    if (canvas) observer.observe(canvas)
    if (chrome) observer.observe(chrome)
    if (header) observer.observe(header)
    window.addEventListener('resize', measure)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [linear, isMobile, canvasAspect])

  useLayoutEffect(() => {
    if (!linearGrid) {
      setGridChrome(null)
      setGridPills(null)
      return undefined
    }
    const measureChrome = () => {
      const next = measurePhoneChrome()
      if (!next) return
      setGridChrome((prev) => {
        if (
          prev
          && Math.abs(prev.viewport.width - next.viewport.width) < 0.5
          && Math.abs(prev.viewport.height - next.viewport.height) < 0.5
          && Math.abs(prev.usable.y - next.usable.y) < 0.5
          && Math.abs(prev.usable.height - next.usable.height) < 0.5
          && Math.abs(prev.usable.width - next.usable.width) < 0.5
        ) return prev
        return next
      })
    }
    measureChrome()
    const observer = new ResizeObserver(measureChrome)
    const canvas = document.querySelector('.observatory canvas')
    const filter = document.querySelector('.observatory .topic-filter')
    const header = document.querySelector('header')
    if (canvas) observer.observe(canvas)
    if (filter) observer.observe(filter)
    if (header) observer.observe(header)
    window.addEventListener('resize', measureChrome)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measureChrome)
    }
  }, [linearGrid, canvasAspect])

  useLayoutEffect(() => {
    if (!linearGrid) return undefined
    const read = () => {
      const nodes = [...document.querySelectorAll('.linear-grid-labels .planet-label')]
      if (nodes.length === 0) return
      const next = nodes.map((node) => {
        const rect = node.getBoundingClientRect()
        const range = document.createRange()
        range.selectNodeContents(node)
        const lines = new Set(
          [...range.getClientRects()]
            .filter((item) => item.height > 0 && item.width > 0)
            .map((item) => Math.round(item.top)),
        ).size
        return {
          topicIndex: Number(node.getAttribute('data-topic-index')),
          width: rect.width,
          height: rect.height,
          lines,
        }
      }).sort((a, b) => a.topicIndex - b.topicIndex)
      setGridPills((prev) => (pillsChanged(prev, next) ? next : prev))
    }
    read()
    const fonts = document.fonts
    if (!fonts?.ready) return undefined
    let cancel = false
    fonts.ready.then(() => {
      if (!cancel) read()
    })
    return () => {
      cancel = true
    }
  }, [linearGrid, topics, layout.pillMaxWidth, canvasAspect])

  const orbitHome = useMemo(() => {
    if (!isMobile || linear) return null
    const frame = orbitFrame ?? estimateOrbitFrame(canvasAspect)
    const samples = orbitSamplePoints(topics, layout)
    const reference = homeLookAt(true, topics.length, layout.extent)
    const referenceDistance = Math.hypot(reference[0], reference[1], reference[2])
    return mobileOrbitHome(layout.extent ?? 12, frame, { samples, referenceDistance })
  }, [isMobile, linear, orbitFrame, canvasAspect, topics, layout])
  const orbitFitKey = orbitHome?.lookAt?.map((value) => Number(value).toFixed(2)).join(',') ?? ''

  const homeFrame = useMemo(
    () => ({
      linear,
      grid: linearGrid,
      viewportAspect: canvasAspect,
      extentX: layout.extentX ?? layout.extent,
      extentY: layout.extentY ?? layout.extent,
      camera: linear ? layout.camera : orbitHome?.lookAt,
    }),
    [linear, linearGrid, canvasAspect, layout.extent, layout.extentX, layout.extentY, layout.camera, orbitHome],
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
    if (!linear) return isMobile ? (orbitHome?.labelDistanceFactor ?? 16) : 18
    if (isMobile) {
      const homeDistance = Math.hypot(home[0], home[1], home[2])
      const portrait = canvasAspect < 0.9
      if (canvasAspect > 1.15) {
        return Math.max(22, homeDistance * 0.96)
      }
      const factor = portrait ? 1.34 : 1.08
      return Math.min(42, Math.max(20, homeDistance * factor))
    }
    return 18
  }, [linear, isMobile, home, canvasAspect, orbitHome])

  useLayoutEffect(() => {
    if (prevLayoutKey.current != null && prevLayoutKey.current !== layoutKey) {
      clearSolarView()
    }
    prevLayoutKey.current = layoutKey
  }, [layoutKey])

  useEffect(() => {
    if (!linear || typeof window === 'undefined') {
      delete window.__perspectiverseLinearLayout
      delete window.__perspectiverseSphereRects
      return undefined
    }
    window.__perspectiverseLinearLayout = {
      mode: layout.mode,
      cols: layout.cols ?? topics.length,
      rows: layout.rows ?? Math.ceil(topics.length / (layout.cols ?? topics.length)),
      positions: layout.positions,
    }
    return () => {
      delete window.__perspectiverseLinearLayout
      delete window.__perspectiverseSphereRects
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
  const landscapeGrid = linearGrid && canvasAspect > 1.15

  return (
    <>
    <section
      className={`observatory${landscapeGrid ? ' is-linear-phone-landscape' : ''}`}
    >
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
          fitKey={orbitFitKey}
        />
      </Canvas>
      {topics.length === 0 && (
        <div className="observatory-empty">
          <p>No planets in {category}.</p>
        </div>
      )}
      {isMobile && !linear && (
        <div className="orbit-labels">
          {topics.map((topic, index) => (
            <button
              key={topic.id}
              type="button"
              data-topic-index={index}
              className="planet-label is-mobile is-orbit"
              style={{ borderColor: hexToRgba(topicColor(topic.id, topic.body), 0.55) }}
              onClick={() => onSelectTopic(topic.id)}
            >
              {topic.name}
            </button>
          ))}
        </div>
      )}
      {linearGrid && layout.screenPlaces && (
        <div className="linear-grid-labels">
          {topics.map((topic, index) => {
            const place = layout.screenPlaces[index]
            if (!place) return null
            return (
              <button
                key={topic.id}
                type="button"
                data-topic-index={index}
                className={`planet-label is-mobile is-linear${landscapeGrid ? ' is-landscape-grid' : ''}`}
                style={{
                  ...gridLabelStyle(canvasAspect, layout.pillMaxWidth),
                  left: place.x,
                  top: place.pillTop,
                  borderColor: hexToRgba(topicColor(topic.id, topic.body), 0.55),
                }}
                onClick={() => onSelectTopic(topic.id)}
              >
                <GridLabelText name={topic.name} landscape={landscapeGrid} />
              </button>
            )
          })}
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
    </>
  )
}
