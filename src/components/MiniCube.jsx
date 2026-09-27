import { Canvas, useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import { topicColor } from '../lib/colors'
import SpikyCube from './SpikyCube'

function SpinningPreview({ topic, selectedPerspectiveId, onSelectPerspective }) {
  const group = useRef()

  useFrame((_, delta) => {
    if (group.current) {
      group.current.rotation.y += delta * 0.7
      group.current.rotation.x += delta * 0.18
    }
  })

  return (
    <group ref={group} scale={1.15}>
      <SpikyCube
        perspectives={topic.perspectives}
        body={topic.body}
        coreColor={topicColor(topic.id, topic.body)}
        selectedPerspectiveId={selectedPerspectiveId}
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
        <SpinningPreview
          topic={topic}
          selectedPerspectiveId={selectedPerspectiveId}
          onSelectPerspective={onSelectPerspective}
        />
      </Canvas>
    </div>
  )
}
