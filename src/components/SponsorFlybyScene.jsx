import { useEffect, useMemo, useRef, useState } from 'react'
import { Billboard, Html } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { Vector3 } from 'three'
import { useSponsorFlybyAnchor } from '../lib/sponsorFlybyContext.js'
import {
  SPONSOR_FLIGHT_SECONDS,
  SPONSOR_IDLE_MAX_SECONDS,
  SPONSOR_IDLE_MIN_SECONDS,
  SPONSOR_TEST_FLIGHT_PROGRESS,
  sponsorFlightPath,
  sponsorFlybyTestLoop,
} from '../lib/sponsorFlybyPath'

const _ndc = new Vector3()

export default function SponsorFlybyScene({ paused = false }) {
  const groupRef = useRef()
  const { setAnchor } = useSponsorFlybyAnchor()
  const { camera, gl } = useThree()
  const testLoop = useMemo(() => sponsorFlybyTestLoop(), [])
  const progress = useRef(testLoop ? SPONSOR_TEST_FLIGHT_PROGRESS : 0)
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
    idleUntil.current = performance.now()
      + (SPONSOR_IDLE_MIN_SECONDS + Math.random() * (SPONSOR_IDLE_MAX_SECONDS - SPONSOR_IDLE_MIN_SECONDS)) * 1000
    return () => {
      setAnchor({ active: false, screenX: 0, screenY: 0, inCanvas: false })
    }
  }, [reduceMotion, testLoop, setAnchor])

  useEffect(() => {
    if (paused || reduceMotion) {
      setAnchor({ active: false, screenX: 0, screenY: 0, inCanvas: false })
    }
  }, [paused, reduceMotion, setAnchor])

  useFrame((_, delta) => {
    if (reduceMotion || paused) return

    if (phase === 'idle') {
      if (!testLoop && performance.now() >= idleUntil.current) {
        setPhase('flying')
        progress.current = 0
      } else {
        setAnchor({ active: false, screenX: 0, screenY: 0, inCanvas: false })
        return
      }
    }

    if (testLoop) {
      progress.current = SPONSOR_TEST_FLIGHT_PROGRESS
    } else {
      progress.current += delta / SPONSOR_FLIGHT_SECONDS
      if (progress.current >= 1) {
        setPhase('idle')
        progress.current = 0
        idleUntil.current = performance.now()
          + (SPONSOR_IDLE_MIN_SECONDS + Math.random() * (SPONSOR_IDLE_MAX_SECONDS - SPONSOR_IDLE_MIN_SECONDS)) * 1000
        setAnchor({ active: false, screenX: 0, screenY: 0, inCanvas: false })
        return
      }
    }

    if (!groupRef.current) return

    const pathPoint = sponsorFlightPath(progress.current)
    groupRef.current.position.copy(pathPoint)
    camera.updateMatrixWorld()
    _ndc.copy(pathPoint).project(camera)

    const inFront = _ndc.z >= -1 && _ndc.z <= 1
    const inFrustum = inFront
      && Math.abs(_ndc.x) <= 1.05
      && Math.abs(_ndc.y) <= 1.05
    const canvasRect = gl.domElement.getBoundingClientRect()
    const screenX = canvasRect.left + (_ndc.x * 0.5 + 0.5) * canvasRect.width
    const screenY = canvasRect.top + (-_ndc.y * 0.5 + 0.5) * canvasRect.height

    setAnchor({
      active: inFrustum,
      screenX,
      screenY,
      inCanvas: inFrustum,
      progress: progress.current,
    })
  })

  if (reduceMotion || paused) return null

  const visible = phase === 'flying' || testLoop
  if (!visible) return null

  return (
    <group ref={groupRef} raycast={() => null}>
      <Billboard follow>
        <Html
          center
          distanceFactor={28}
          zIndexRange={[3, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div className="sponsor-flyby-ship" aria-hidden="true" data-sponsor-ship="" />
        </Html>
      </Billboard>
    </group>
  )
}
