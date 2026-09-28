import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { AdditiveBlending, DoubleSide } from 'three'
import { shadeHex } from '../lib/colors'
import { CORE_RADIUS } from '../lib/faces'
import { createBodyTexture, createRingTexture } from '../lib/planetTextures'
import { buildCrystal } from '../lib/spikes'

function SaturnRings({ meshRef, quality = 'high' }) {
  const texture = useMemo(() => createRingTexture(quality), [quality])
  // Cached globally — do not dispose on unmount.

  return (
    <mesh ref={meshRef} rotation={[Math.PI / 2.15, 0.18, 0]} raycast={() => null}>
      <ringGeometry args={[1.02, 1.72, 80]} />
      <meshBasicMaterial
        map={texture}
        transparent
        opacity={0.92}
        side={DoubleSide}
        depthWrite={false}
      />
    </mesh>
  )
}

function SunCorona({ meshRef, color, detail }) {
  return (
    <group ref={meshRef} raycast={() => null}>
      <mesh raycast={() => null} renderOrder={1}>
        <sphereGeometry args={[CORE_RADIUS * 1.06, detail[0], detail[1]]} />
        <meshBasicMaterial
          color="#fff6c8"
          transparent
          opacity={0.42}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh raycast={() => null} renderOrder={1}>
        <sphereGeometry args={[CORE_RADIUS * 1.18, Math.max(16, detail[0] - 8), Math.max(12, detail[1] - 8)]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.2}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
    </group>
  )
}

export default function SpikyCube({
  perspectives = [],
  body = null,
  coreColor = '#f4c14e',
  selectedPerspectiveId = null,
  dimmed = false,
  showSpikes = true,
  onSelectPerspective,
  interactive = true,
  quality = 'high',
  sphereDetail = [48, 36],
}) {
  const reveal = useRef(showSpikes ? 1 : 0)
  const sphereMat = useRef()
  const sphereMesh = useRef()
  const crystal = useRef()
  const ringMat = useRef()
  const ringMesh = useRef()
  const corona = useRef()
  const [crystalReady, setCrystalReady] = useState(showSpikes)
  const pigment = body?.color ?? coreColor
  const isSun = body?.key === 'sun'
  const color = pigment
  const emissive = dimmed ? 0.02 : isSun ? 1.8 : 0.035
  const emissiveColor = dimmed ? '#6b7280' : isSun ? '#fff3c2' : '#fff4dc'

  const texture = useMemo(
    () => createBodyTexture(body?.key ?? 'mercury', quality),
    [body?.key, quality],
  )
  const crystalGeo = useMemo(
    () => (crystalReady ? buildCrystal(perspectives, { quality, pigment }) : null),
    [crystalReady, perspectives, quality, pigment],
  )

  useEffect(() => {
    if (showSpikes) setCrystalReady(true)
  }, [showSpikes])

  useEffect(() => () => {
    if (!crystalGeo) return
    crystalGeo.core.dispose()
    for (const face of crystalGeo.faces) {
      face.extrusion.dispose()
      face.pick.dispose()
    }
  }, [crystalGeo])

  useFrame((_, delta) => {
    const target = showSpikes && !dimmed ? 1 : 0
    reveal.current += (target - reveal.current) * Math.min(1, delta * 5.2)
    const amount = reveal.current
    if (sphereMat.current) {
      const opacity = dimmed ? 0.16 : 1 - amount
      sphereMat.current.opacity = opacity
      sphereMat.current.transparent = opacity < 0.985
      sphereMat.current.depthWrite = opacity > 0.4
    }
    if (sphereMesh.current) {
      sphereMesh.current.scale.setScalar(1 - amount * 0.05)
      sphereMesh.current.visible = amount < 0.97
    }
    if (crystal.current) {
      crystal.current.visible = amount > 0.02
      crystal.current.scale.setScalar(0.9 + amount * 0.1)
    }
    if (ringMat.current) {
      ringMat.current.opacity = (1 - amount) * 0.92
    }
    if (ringMesh.current) {
      ringMesh.current.visible = !dimmed && amount < 0.97
    }
    if (corona.current) {
      corona.current.visible = isSun && !dimmed && amount < 0.85
    }
  })

  const faces = crystalGeo
    ? [...crystalGeo.faces].sort((a, b) => b.opacity - a.opacity)
    : []

  return (
    <group>
      <mesh ref={sphereMesh} renderOrder={0}>
        <sphereGeometry args={[CORE_RADIUS, sphereDetail[0], sphereDetail[1]]} />
        {isSun ? (
          <meshBasicMaterial
            ref={sphereMat}
            map={texture}
            color={dimmed ? '#6b7280' : '#ffffff'}
            toneMapped={false}
            transparent={dimmed}
            opacity={dimmed ? 0.16 : 1}
          />
        ) : (
          <meshStandardMaterial
            ref={sphereMat}
            map={texture}
            color={dimmed ? '#6b7280' : '#ffffff'}
            emissive={emissiveColor}
            emissiveIntensity={emissive}
            roughness={body?.key === 'mercury' ? 0.48 : 0.58}
            metalness={body?.key === 'mercury' ? 0.22 : 0.06}
            transparent={dimmed}
            opacity={dimmed ? 0.16 : 1}
          />
        )}
      </mesh>
      {isSun && !dimmed && (
        <SunCorona meshRef={corona} color={color} detail={sphereDetail} />
      )}
      {body?.rings && (
        <SaturnRings
          quality={quality}
          meshRef={(node) => {
            ringMesh.current = node
            ringMat.current = node?.material ?? null
          }}
        />
      )}
      {crystalGeo && (
        <group ref={crystal}>
          <mesh geometry={crystalGeo.core} raycast={() => null}>
            <meshStandardMaterial
              color={shadeHex(pigment, 0.42)}
              emissive={pigment}
              emissiveIntensity={0.18}
              roughness={0.4}
              metalness={0.16}
            />
          </mesh>
          {faces.map((face) => {
            const selected = selectedPerspectiveId === face.id
            const transparent = face.opacity < 0.98
            return (
              <group key={face.id} scale={selected ? 1.05 : 1}>
                {interactive && (
                  <mesh
                    geometry={face.pick}
                    onClick={
                      onSelectPerspective
                        ? (event) => {
                            event.stopPropagation()
                            onSelectPerspective(face.id)
                          }
                        : undefined
                    }
                    onPointerOver={(event) => {
                      event.stopPropagation()
                      document.body.style.cursor = 'pointer'
                    }}
                    onPointerOut={() => {
                      document.body.style.cursor = 'auto'
                    }}
                  >
                    <meshBasicMaterial transparent opacity={0} depthWrite={false} />
                  </mesh>
                )}
                <mesh geometry={face.extrusion} raycast={() => null}>
                  <meshStandardMaterial
                    color={face.color}
                    emissive={face.color}
                    emissiveIntensity={selected ? 1.15 : 0.16 + face.opacity * 0.28}
                    roughness={0.34}
                    metalness={0.06}
                    side={DoubleSide}
                    toneMapped={false}
                    transparent={transparent}
                    opacity={face.opacity}
                    depthWrite={!transparent}
                    polygonOffset
                    polygonOffsetFactor={-1}
                    polygonOffsetUnits={-1}
                  />
                </mesh>
              </group>
            )
          })}
        </group>
      )}
    </group>
  )
}
