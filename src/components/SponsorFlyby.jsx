import { useEffect, useMemo, useRef, useState } from 'react'
import { Billboard, Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { Vector3 } from 'three'

export const SPONSOR_BANNER_TEXT = 'Does Advertising Work? Just Did!'

const FLIGHT_SECONDS = 16
const IDLE_MIN_SECONDS = 50
const IDLE_MAX_SECONDS = 95

function flightPath(t) {
  const x = -58 + t * 116
  const y = 6 + Math.sin(t * Math.PI) * 4.5
  const z = 18 - t * 42 + Math.sin(t * Math.PI * 2) * 6
  return new Vector3(x, y, z)
}

function sponsorFlybyTestLoop() {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).has('sponsorFlyby')
}

export default function SponsorFlyby() {
  const groupRef = useRef()
  const testLoop = useMemo(() => sponsorFlybyTestLoop(), [])
  const progress = useRef(testLoop ? 0.45 : 0)
  const reduceMotion = useMemo(
    () => (typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false),
    [],
  )
  const [phase, setPhase] = useState(() => (testLoop ? 'flying' : 'idle'))
  const idleUntil = useRef(0)

  useEffect(() => {
    if (reduceMotion || testLoop) return undefined
    idleUntil.current = performance.now() + (IDLE_MIN_SECONDS + Math.random() * (IDLE_MAX_SECONDS - IDLE_MIN_SECONDS)) * 1000
    return undefined
  }, [reduceMotion, testLoop])

  useFrame((_, delta) => {
    if (reduceMotion || phase === 'idle') {
      if (!testLoop && phase === 'idle' && performance.now() >= idleUntil.current) {
        setPhase('flying')
        progress.current = 0
      }
      return
    }

    const speed = testLoop ? 1 / 8 : 1 / FLIGHT_SECONDS
    progress.current += delta * speed
    if (progress.current >= 1) {
      if (testLoop) {
        progress.current = 0
      } else {
        setPhase('idle')
        progress.current = 0
        idleUntil.current = performance.now()
          + (IDLE_MIN_SECONDS + Math.random() * (IDLE_MAX_SECONDS - IDLE_MIN_SECONDS)) * 1000
        return
      }
    }

    if (groupRef.current) {
      groupRef.current.position.copy(flightPath(progress.current))
    }
  })

  if (reduceMotion) return null

  const visible = phase === 'flying' || testLoop
  if (!visible) return null

  const t = progress.current
  const inView = t > 0.01 && t < 0.99

  return (
    <group ref={groupRef} raycast={() => null}>
      <Billboard follow lockX={false} lockY={false} lockZ={false}>
      <Html
        center
        distanceFactor={22}
        zIndexRange={[4, 0]}
        style={{ pointerEvents: 'none' }}
      >
        <div
          className={`sponsor-flyby ${inView ? 'is-midflight' : ''}`}
          aria-hidden="true"
          data-sponsor-flyby={inView ? 'visible' : 'transition'}
        >
          <div className="sponsor-flyby-ship" />
          <div className="sponsor-flyby-towline" />
          <p className="sponsor-flyby-banner">{SPONSOR_BANNER_TEXT}</p>
        </div>
      </Html>
      </Billboard>
    </group>
  )
}
