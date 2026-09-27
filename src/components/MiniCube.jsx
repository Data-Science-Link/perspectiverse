import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import { Quaternion, Vector3 } from 'three'
import { rankPerspectives, topicColor } from '../lib/colors'
import { faceLayout } from '../lib/faces'
import SpikyCube from './SpikyCube'

const CAMERA = new Vector3(3.4, 2.0, 3.4).normalize()
const _look = new Vector3()
const _target = new Quaternion()

function Preview({ topic, selectedPerspectiveId, onSelectPerspective }) {
  const group = useRef()
  const ranked = useMemo(
    () => rankPerspectives(topic.perspectives),
    [topic.perspectives],
  )
  const layout = useMemo(() => faceLayout(ranked.length), [ranked.length])
  const focusIndex = ranked.findIndex((face) => face.id === selectedPerspectiveId)

  useFrame((_, delta) => {
    if (!group.current) return
    if (focusIndex >= 0 && layout[focusIndex]) {
      _look.set(...layout[focusIndex].direction)
      _target.setFromUnitVectors(_look, CAMERA)
      group.current.quaternion.slerp(_target, 1 - Math.exp(-delta * 6))
      return
    }
    group.current.rotation.y += delta * 0.7
    group.current.rotation.x += delta * 0.18
  })

  return (
    <group ref={group} scale={1.15}>
      <SpikyCube
        perspectives={topic.perspectives}
        body={topic.body}
        coreColor={topicColor(topic.id, topic.body)}
        selectedPerspectiveId={selectedPerspectiveId}
        showSpikes
        onSelectPerspective={onSelectPerspective}
      />
    </group>
  )
}

export default function MiniCube({ topic, selectedPerspectiveId, onSelectPerspective }) {
  return (
    <div className="mini-cube">
      <Canvas camera={{ position: [3.4, 2.0, 3.4], fov: 38 }} dpr={[1, 1.5]}>
        <ambientLight intensity={0.7} />
        <pointLight position={[2, 3, 2]} intensity={1.6} color="#fff1c2" />
        <directionalLight position={[-2, 2, 3]} intensity={0.6} />
        <Preview
          topic={topic}
          selectedPerspectiveId={selectedPerspectiveId}
          onSelectPerspective={onSelectPerspective}
        />
      </Canvas>
    </div>
  )
}
