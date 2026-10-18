import { useEffect, useMemo, useRef, useState } from 'react'
import { Billboard, Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { Vector3 } from 'three'

export const SPONSOR_BANNER_TEXT = 'Does Advertising Work? Just Did!'
export const SPONSOR_BANNER_MIN_SCREEN_PX = 14

const FLIGHT_SECONDS = 16
const IDLE_MIN_SECONDS = 50
const IDLE_MAX_SECONDS = 95
const TEST_FLIGHT_PROGRESS = 0.55
/** Html scale grows with distanceFactor; scale with camera distance for constant screen size. */
const BANNER_FACTOR_PER_DISTANCE = 0.125

const _world = new Vector3()

/** Mid-field path: close enough to read the banner, still often behind planets. */
function flightPath(t) {
  const x = -44 + t * 88
  const y = 11 + Math.sin(t * Math.PI) * 3.5
  const z = 46 - t * 14 + Math.sin(t * Math.PI * 2) * 5
  return new Vector3(x, y, z)
}

function sponsorFlybyTestLoop() {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).has('sponsorFlyby')
}

export default function SponsorFlyby() {
  const groupRef = useRef()
  const bannerRef = useRef(null)
  const bannerDistanceFactorRef = useRef(6.5)
  const [bannerDistanceFactor, setBannerDistanceFactor] = useState(6.5)
  const testLoop = useMemo(() => sponsorFlybyTestLoop(), [])
  const progress = useRef(testLoop ? TEST_FLIGHT_PROGRESS : 0)
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

  useFrame((state, delta) => {
    if (reduceMotion || phase === 'idle') {
      if (!testLoop && phase === 'idle' && performance.now() >= idleUntil.current) {
        setPhase('flying')
        progress.current = 0
      }
      return
    }

    if (testLoop) {
      progress.current = TEST_FLIGHT_PROGRESS
    } else {
      const speed = 1 / FLIGHT_SECONDS
      progress.current += delta * speed
      if (progress.current >= 1) {
        setPhase('idle')
        progress.current = 0
        idleUntil.current = performance.now()
          + (IDLE_MIN_SECONDS + Math.random() * (IDLE_MAX_SECONDS - IDLE_MIN_SECONDS)) * 1000
        return
      }
    }

    if (!groupRef.current) return

    groupRef.current.position.copy(flightPath(progress.current))
    groupRef.current.getWorldPosition(_world)
    const distance = state.camera.position.distanceTo(_world)
    let factor = distance * BANNER_FACTOR_PER_DISTANCE
    factor = Math.min(12, Math.max(6.2, factor))

    const bannerEl = bannerRef.current
    if (bannerEl) {
      const screenHeight = bannerEl.getBoundingClientRect().height
      if (screenHeight > 0 && screenHeight < SPONSOR_BANNER_MIN_SCREEN_PX) {
        factor = Math.min(12, factor * 1.08)
      }
    }

    if (Math.abs(factor - bannerDistanceFactorRef.current) > 0.05) {
      bannerDistanceFactorRef.current = factor
      setBannerDistanceFactor(factor)
    }
  })

  if (reduceMotion) return null

  const visible = phase === 'flying' || testLoop
  if (!visible) return null

  const t = progress.current
  const inView = t > 0.01 && t < 0.99

  return (
    <group ref={groupRef} raycast={() => null}>
      <Billboard follow>
        <Html
          position={[-1.05, 0, 0]}
          center
          distanceFactor={26}
          zIndexRange={[4, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div className="sponsor-flyby-ship" aria-hidden="true" />
        </Html>
      </Billboard>
      <Billboard follow>
        <Html
          position={[0.35, 0, 0]}
          center
          distanceFactor={bannerDistanceFactor}
          zIndexRange={[4, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div
            className={`sponsor-flyby-banner-wrap ${inView ? 'is-midflight' : ''}`}
            aria-hidden="true"
            data-sponsor-flyby={inView ? 'visible' : 'transition'}
          >
            <span className="sponsor-flyby-towline" />
            <p ref={bannerRef} className="sponsor-flyby-banner">{SPONSOR_BANNER_TEXT}</p>
          </div>
        </Html>
      </Billboard>
    </group>
  )
}
