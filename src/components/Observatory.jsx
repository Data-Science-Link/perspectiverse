import { useEffect, useRef } from 'react'
import { CameraControls, Stars } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { cameraOffsetForScale, topicScale } from '../lib/layout'
import { OrbitRing, default as Planet } from './Planet'

const HOME_VIEW = [0, 8.6, 21.5, 0, 0, 0]

function FocusCamera({ controlsRef, anchors, selectedTopic }) {
  const lastId = useRef(null)

  useFrame(() => {
    const controls = controlsRef.current
    if (!controls) return

    if (!selectedTopic) {
      if (lastId.current !== null) {
        controls.setLookAt(...HOME_VIEW, true)
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
  onSelectTopic,
  onSelectPerspective,
}) {
  const controlsRef = useRef()
  const anchors = useRef({})
  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null

  useEffect(() => {
    return () => {
      document.body.style.cursor = 'auto'
    }
  }, [])

  return (
    <>
      <color attach="background" args={['#05060b']} />
      <fog attach="fog" args={['#05060b', 26, 72]} />
      <ambientLight intensity={0.28} />
      <pointLight position={[0, 0, 0]} intensity={2.4} distance={42} color="#ffe7a3" />
      <pointLight position={[12, 14, 8]} intensity={0.55} color="#9db7ff" />
      <Stars radius={90} depth={42} count={4500} factor={3.4} saturation={0} fade speed={0.35} />
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
        />
      ))}
      <CameraControls
        ref={controlsRef}
        makeDefault
        minDistance={3.2}
        maxDistance={46}
        dollyToCursor
        smoothTime={0.35}
      />
      <FocusCamera controlsRef={controlsRef} anchors={anchors} selectedTopic={selectedTopic} />
      <EffectComposer disableNormalPass>
        <Bloom intensity={0.55} luminanceThreshold={0.28} luminanceSmoothing={0.4} mipmapBlur />
      </EffectComposer>
    </>
  )
}

export default function Observatory({
  topics,
  selectedTopicId,
  selectedPerspectiveId,
  onSelectTopic,
  onSelectPerspective,
  onClearSelection,
}) {
  return (
    <section className="observatory">
      <Canvas
        camera={{ position: [0, 8.6, 21.5], fov: 42, near: 0.1, far: 120 }}
        dpr={[1, 1.75]}
        onPointerMissed={onClearSelection}
      >
        <Universe
          topics={topics}
          selectedTopicId={selectedTopicId}
          selectedPerspectiveId={selectedPerspectiveId}
          onSelectTopic={onSelectTopic}
          onSelectPerspective={onSelectPerspective}
        />
      </Canvas>
      <div className="observatory-chrome">
        <p>Drag to orbit · Scroll to zoom · Click a planet or a spike</p>
      </div>
    </section>
  )
}
