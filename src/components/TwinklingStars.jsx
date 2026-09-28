import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { AdditiveBlending } from 'three'

const vertexShader = `
  attribute float aPhase;
  attribute float aSize;
  attribute float aTint;
  uniform float uTime;
  varying float vTwinkle;
  varying float vTint;
  void main() {
    float pulse = 0.72 + 0.28 * sin(uTime * (0.7 + aPhase * 0.15) + aPhase);
    vTwinkle = pulse;
    vTint = aTint;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * pulse * (280.0 / max(1.0, -mv.z));
    gl_Position = projectionMatrix * mv;
  }
`

const fragmentShader = `
  varying float vTwinkle;
  varying float vTint;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float core = smoothstep(0.5, 0.08, d);
    vec3 cool = vec3(0.86, 0.90, 1.0);
    vec3 warm = vec3(1.0, 0.92, 0.78);
    vec3 color = mix(cool, warm, vTint);
    gl_FragColor = vec4(color, core * vTwinkle);
  }
`

export default function TwinklingStars({ count = 480, radius = 76 }) {
  const material = useRef()
  const reduceMotion = useMemo(
    () => (typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false),
    [],
  )

  const { positions, phases, sizes, tints } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const phases = new Float32Array(count)
    const sizes = new Float32Array(count)
    const tints = new Float32Array(count)
    for (let i = 0; i < count; i += 1) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = radius * (0.52 + Math.random() * 0.48)
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.cos(phi)
      positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta)
      phases[i] = Math.random() * Math.PI * 2
      sizes[i] = 1.05 + Math.random() * 2.15
      tints[i] = Math.random()
    }
    return { positions, phases, sizes, tints }
  }, [count, radius])

  useFrame((state) => {
    if (!material.current || reduceMotion) return
    material.current.uniforms.uTime.value = state.clock.elapsedTime
  })

  return (
    <points frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-aPhase" args={[phases, 1]} />
        <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
        <bufferAttribute attach="attributes-aTint" args={[tints, 1]} />
      </bufferGeometry>
      <shaderMaterial
        ref={material}
        transparent
        depthWrite={false}
        blending={AdditiveBlending}
        toneMapped={false}
        uniforms={{ uTime: { value: 0 } }}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
      />
    </points>
  )
}
