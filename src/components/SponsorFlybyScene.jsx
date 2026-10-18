import { useEffect, useMemo, useRef, useState } from 'react'
import { Billboard, Html } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { Vector3 } from 'three'
import { sponsorFlybyAnchorRef } from '../lib/sponsorFlybyAnchorRef.js'
import {
  SPONSOR_FLIGHT_SECONDS,
  SPONSOR_IDLE_MAX_SECONDS,
  SPONSOR_IDLE_MIN_SECONDS,
  SPONSOR_TEST_FLIGHT_PROGRESS,
  sponsorFlightPath,
  sponsorFlybyQueryMode,
} from '../lib/sponsorFlybyPath'

const _ndc = new Vector3()
const _world = new Vector3()

export default function SponsorFlybyScene({ paused = false }) {
  const groupRef = useRef()
  const { camera, gl } = useThree()
  const flybyMode = useMemo(() => sponsorFlybyQueryMode(), [])
  const progress = useRef(flybyMode.pin ? SPONSOR_TEST_FLIGHT_PROGRESS : 0)
  const reduceMotion = useMemo(
    () => (typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false),
    [],
  )
  const [phase, setPhase] = useState(() => (flybyMode.enabled ? 'flying' : 'idle'))
  const idleUntil = useRef(0)

  useEffect(() => {
    if (reduceMotion || flybyMode.enabled) return undefined
    idleUntil.current = performance.now()
      + (SPONSOR_IDLE_MIN_SECONDS + Math.random() * (SPONSOR_IDLE_MAX_SECONDS - SPONSOR_IDLE_MIN_SECONDS)) * 1000
    return () => {
      sponsorFlybyAnchorRef.current = {
        active: false, screenX: 0, screenY: 0, inCanvas: false, progress: 0,
      }
    }
  }, [reduceMotion, flybyMode.enabled])

  useEffect(() => {
    if (paused || reduceMotion) {
      sponsorFlybyAnchorRef.current = {
        active: false, screenX: 0, screenY: 0, inCanvas: false, progress: 0,
      }
    }
  }, [paused, reduceMotion])

  useFrame((_, delta) => {
    if (reduceMotion || paused) return

    if (phase === 'idle') {
      if (!flybyMode.enabled && performance.now() >= idleUntil.current) {
        setPhase('flying')
        progress.current = 0
      } else {
        sponsorFlybyAnchorRef.current = {
          active: false, screenX: 0, screenY: 0, inCanvas: false, progress: 0,
        }
        return
      }
    }

    if (flybyMode.animate) {
      progress.current += delta / SPONSOR_FLIGHT_SECONDS
      if (progress.current >= 1) progress.current = 0
    } else if (flybyMode.pin) {
      progress.current = flybyMode.pinProgress
    } else {
      progress.current += delta / SPONSOR_FLIGHT_SECONDS
      if (progress.current >= 1) {
        setPhase('idle')
        progress.current = 0
        idleUntil.current = performance.now()
          + (SPONSOR_IDLE_MIN_SECONDS + Math.random() * (SPONSOR_IDLE_MAX_SECONDS - SPONSOR_IDLE_MIN_SECONDS)) * 1000
        sponsorFlybyAnchorRef.current = {
          active: false, screenX: 0, screenY: 0, inCanvas: false, progress: 0,
        }
        return
      }
    }

    if (!groupRef.current) return

    const pathPoint = sponsorFlightPath(progress.current)
    groupRef.current.position.copy(pathPoint)
    groupRef.current.updateWorldMatrix(true, false)
    camera.updateMatrixWorld()
    groupRef.current.getWorldPosition(_world)
    _ndc.copy(_world).project(camera)

    const inFront = _ndc.z >= -1 && _ndc.z <= 1
    const inFrustum = inFront
      && Math.abs(_ndc.x) <= 1.05
      && Math.abs(_ndc.y) <= 1.05
    const canvasRect = gl.domElement.getBoundingClientRect()
    const screenX = canvasRect.left + (_ndc.x * 0.5 + 0.5) * canvasRect.width
    const screenY = canvasRect.top + (-_ndc.y * 0.5 + 0.5) * canvasRect.height

    sponsorFlybyAnchorRef.current = {
      active: inFrustum,
      screenX,
      screenY,
      inCanvas: inFrustum,
      progress: progress.current,
    }
  })

  if (reduceMotion || paused) return null

  const visible = phase === 'flying' || flybyMode.enabled
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
