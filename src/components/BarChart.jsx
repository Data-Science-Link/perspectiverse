import { useMemo } from 'react'
import { formatPercent } from '../lib/layout'
import { createBodyTexture } from '../lib/planetTextures'

function skinUrl(key) {
  const texture = createBodyTexture(key || 'mercury', 'low')
  const source = texture.image
  if (!source || typeof source.toDataURL !== 'function') return ''
  const band = Math.max(18, Math.round(source.height * 0.34))
  const slice = document.createElement('canvas')
  slice.width = source.width
  slice.height = band
  const context = slice.getContext('2d')
  const start = Math.round((source.height - band) / 2)
  context.drawImage(source, 0, start, source.width, band, 0, 0, slice.width, slice.height)
  return slice.toDataURL('image/png')
}

export default function BarChart({ bars, selectedId, onSelect }) {
  const max = Math.max(...bars.map((bar) => Number(bar.value) || 0), 1)
  const skins = useMemo(() => {
    const urls = {}
    for (const bar of bars) {
      const key = bar.textureKey || 'mercury'
      if (!urls[key]) urls[key] = skinUrl(key)
    }
    return urls
  }, [bars])
  const few = bars.length <= 3

  return (
    <div className={`bar-chart ${few ? 'is-few' : 'is-many'}`}>
      {bars.map((bar) => {
        const selected = bar.id === selectedId
        const share = Math.max(0, Number(bar.value) || 0) / max
        const skin = skins[bar.textureKey || 'mercury'] || ''
        return (
          <button
            key={bar.id}
            type="button"
            className={`bar-name ${selected ? 'is-selected' : ''}`}
            aria-pressed={selected}
            style={{
              '--bar-color': bar.color || '#f4c14e',
              '--share': share,
              '--skin': skin ? `url("${skin}")` : 'none',
            }}
            onClick={() => onSelect(bar.id)}
          >
            <span className="bar-copy">
              <span className="bar-label">{bar.label}</span>
              <strong>{formatPercent(bar.value)}</strong>
            </span>
            <span className="bar-prism" aria-hidden="true" />
          </button>
        )
      })}
    </div>
  )
}
