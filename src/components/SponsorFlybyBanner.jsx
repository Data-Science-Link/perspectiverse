import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useSponsorFlybyAnchor } from '../lib/sponsorFlybyContext.js'

export const SPONSOR_BANNER_TEXT = 'Does Advertising Work? Just Did!'
export const SPONSOR_BANNER_MIN_SCREEN_PX = 14

function rectsOverlap(a, b) {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

export default function SponsorFlybyBanner({ paused = false }) {
  const { anchor } = useSponsorFlybyAnchor()
  const wrapRef = useRef(null)
  const [placement, setPlacement] = useState({ left: 0, top: 0, opacity: 1, visible: false })

  const reduceMotion = useMemo(
    () => (typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false),
    [],
  )

  useLayoutEffect(() => {
    if (reduceMotion || paused || !anchor.active || !anchor.inCanvas) {
      setPlacement((prev) => (prev.visible ? { ...prev, visible: false, opacity: 0 } : prev))
      return
    }

    const observatory = document.querySelector('.observatory')
    const canvas = observatory?.querySelector('canvas')
    const chrome = document.querySelector('.site-chrome')
    const wrap = wrapRef.current
    if (!observatory || !canvas || !wrap) return

    const canvasRect = canvas.getBoundingClientRect()
    const headerBottom = chrome?.getBoundingClientRect().bottom ?? 0
    const chromeRow = observatory.querySelector('.observatory-chrome')
    const chromeTop = chromeRow?.getBoundingClientRect().top ?? canvasRect.bottom

    const pad = 10
    const topLimit = Math.max(canvasRect.top + pad, headerBottom + pad)
    const bottomLimit = Math.min(canvasRect.bottom - pad, chromeTop - pad)
    const leftLimit = canvasRect.left + pad
    const rightLimit = canvasRect.right - pad

    const shipX = anchor.screenX
    const shipY = anchor.screenY
    const bannerWidth = wrap.offsetWidth || 280
    const bannerHeight = wrap.offsetHeight || 22
    const towGap = 12
    let left = shipX + towGap + bannerWidth / 2
    let top = shipY

    if (left + bannerWidth / 2 > rightLimit) {
      left = shipX - towGap - bannerWidth / 2
    }

    left = clamp(left, leftLimit + bannerWidth / 2, rightLimit - bannerWidth / 2)
    top = clamp(top, topLimit + bannerHeight / 2, bottomLimit - bannerHeight / 2)

    const bannerRect = {
      left: left - bannerWidth / 2,
      right: left + bannerWidth / 2,
      top: top - bannerHeight / 2,
      bottom: top + bannerHeight / 2,
    }

    let opacity = 1
    observatory.querySelectorAll('.planet-label').forEach((label) => {
      if (rectsOverlap(bannerRect, label.getBoundingClientRect())) {
        opacity = 0.22
      }
    })

    setPlacement({ left, top, opacity, visible: true })
  }, [anchor, paused, reduceMotion])

  if (reduceMotion || paused || !anchor.active) return null

  return (
    <div
      ref={wrapRef}
      className="sponsor-flyby-screen"
      style={{
        left: placement.visible ? placement.left : anchor.screenX,
        top: placement.visible ? placement.top : anchor.screenY,
        opacity: placement.visible ? placement.opacity : 0,
        visibility: placement.visible ? 'visible' : 'hidden',
        transform: 'translate(-50%, -50%)',
      }}
      aria-hidden="true"
      data-sponsor-flyby={placement.visible ? 'visible' : 'measuring'}
    >
      <span className="sponsor-flyby-towline sponsor-flyby-towline--screen" />
      <p className="sponsor-flyby-banner">
        <span className="sponsor-flyby-banner-text">{SPONSOR_BANNER_TEXT}</span>
      </p>
    </div>
  )
}
