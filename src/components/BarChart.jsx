import { useMemo } from 'react'
import { formatPercent } from '../lib/layout'
import { createBodyTexture } from '../lib/planetTextures'

function skinUrl(key) {
  const texture = createBodyTexture(key || 'mercury', 'low')
  const canvas = texture.image
  if (!canvas || typeof canvas.toDataURL !== 'function') return ''
  return canvas.toDataURL('image/jpeg', 0.86)
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
      {bars.map((bar, index) => {
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
              '--shift': `${index * 22}%`,
            }}
            onClick={() => onSelect(bar.id)}
          >
            <span className="bar-copy">
              <span className="bar-label">{bar.label}</span>
              <strong>{formatPercent(bar.value)}</strong>
            </span>
            <span className="bar-prism" aria-hidden="true">
              <span className="bar-shine" />
            </span>
          </button>
        )
      })}
    </div>
  )
}
