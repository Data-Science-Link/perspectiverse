import { useEffect, useMemo, useRef } from 'react'
import { sponsorFlybyAnchorRef } from '../lib/sponsorFlybyAnchorRef.js'
import { pillOpacityForLabels, towSideForShip } from '../lib/sponsorFlybyPlacement.js'

export const SPONSOR_BANNER_TEXT = 'Does Advertising Work? Just Did!'
export const SPONSOR_BANNER_MIN_SCREEN_PX = 14

export default function SponsorFlybyBanner({ paused = false, linear = false, linearGrid = false }) {
  const screenRef = useRef(null)
  const rowRef = useRef(null)
  const pillRef = useRef(null)
  const towSideRef = useRef('right')

  const reduceMotion = useMemo(
    () => (typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false),
    [],
  )

  useEffect(() => {
    if (reduceMotion || paused) return undefined

    let frame = 0
    const positionBanner = () => {
      const screen = screenRef.current
      const row = rowRef.current
      const pill = pillRef.current
      const anchor = sponsorFlybyAnchorRef.current
      if (!screen || !row || !pill) return

      if (!anchor.active || !anchor.inCanvas) {
        screen.style.visibility = 'hidden'
        screen.removeAttribute('data-sponsor-flyby')
        return
      }

      const observatory = document.querySelector('.observatory')
      const canvas = observatory?.querySelector('canvas')
      const chrome = document.querySelector('.site-chrome')
      if (!observatory || !canvas) return

      const canvasRect = canvas.getBoundingClientRect()
      const headerBottom = chrome?.getBoundingClientRect().bottom ?? 0
      const chromeRow = observatory.querySelector('.observatory-chrome')
      let chromeTop = chromeRow?.getBoundingClientRect().top ?? canvasRect.bottom
      if (linear && linearGrid) {
        const filterLabel = observatory.querySelector('.topic-filter span')
        const filterTop = filterLabel?.getBoundingClientRect().top
          ?? document.getElementById('solar-topic-filter')?.getBoundingClientRect().top
        if (filterTop) chromeTop = Math.min(chromeTop, filterTop - 12)
      }
      const pad = 10
      const bounds = {
        left: canvasRect.left + pad,
        right: canvasRect.right - pad,
        top: Math.max(canvasRect.top + pad, headerBottom + pad),
        bottom: Math.min(canvasRect.bottom - pad, chromeTop - pad),
      }

      const sceneShip = document.querySelector('[data-sponsor-ship-scene]')
      let shipX = anchor.screenX
      let shipY = anchor.screenY
      let shipHalfW = 7
      if (sceneShip) {
        const shipRect = sceneShip.getBoundingClientRect()
        if (shipRect.width > 0 && shipRect.height > 0) {
          shipX = shipRect.left + shipRect.width / 2
          shipY = shipRect.top + shipRect.height / 2
          shipHalfW = shipRect.width / 2
        }
      }

      const rowWidth = row.offsetWidth || 240
      const side = towSideForShip(shipX, rowWidth, bounds, towSideRef.current)
      towSideRef.current = side
      row.classList.toggle('is-left', side === 'left')

      const originX = side === 'right' ? shipX - shipHalfW : shipX + shipHalfW
      screen.style.left = `${originX}px`
      screen.style.top = `${shipY}px`
      screen.style.visibility = 'visible'
      screen.dataset.sponsorFlyby = 'visible'
      screen.dataset.sponsorShipX = String(shipX)
      screen.dataset.sponsorShipY = String(shipY)

      const pillRect = pill.getBoundingClientRect()
      const labelRects = [...observatory.querySelectorAll('.planet-label')].map(
        (label) => label.getBoundingClientRect(),
      )
      pill.style.opacity = String(pillOpacityForLabels(pillRect, labelRects))
    }

    const tick = () => {
      frame = requestAnimationFrame(() => {
        positionBanner()
        tick()
      })
    }

    tick()
    return () => cancelAnimationFrame(frame)
  }, [linear, linearGrid, paused, reduceMotion])

  if (reduceMotion || paused) return null

  return (
    <div
      ref={screenRef}
      className="sponsor-flyby-screen"
      style={{ visibility: 'hidden' }}
      aria-hidden="true"
    >
      <div ref={rowRef} className="sponsor-flyby-tow-row">
        <span className="sponsor-flyby-ship" data-sponsor-ship="" aria-hidden="true" />
        <span className="sponsor-flyby-towline sponsor-flyby-towline--screen" />
        <p ref={pillRef} className="sponsor-flyby-banner">
          <span className="sponsor-flyby-banner-text">{SPONSOR_BANNER_TEXT}</span>
        </p>
      </div>
    </div>
  )
}
