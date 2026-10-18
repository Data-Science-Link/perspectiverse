import { useMemo, useState } from 'react'
import { SponsorFlybyContext } from '../lib/sponsorFlybyContext.js'

export default function SponsorFlybyProvider({ children }) {
  const [anchor, setAnchor] = useState({
    active: false,
    screenX: 0,
    screenY: 0,
    inCanvas: false,
  })
  const value = useMemo(() => ({ anchor, setAnchor }), [anchor])
  return (
    <SponsorFlybyContext.Provider value={value}>
      {children}
    </SponsorFlybyContext.Provider>
  )
}
