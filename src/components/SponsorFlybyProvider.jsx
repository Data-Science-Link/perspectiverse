import { useMemo, useState } from 'react'
import { SponsorFlybyContext } from '../lib/sponsorFlybyContext.js'

export default function SponsorFlybyProvider({ children }) {
  const [tick, setTick] = useState(0)
  const value = useMemo(() => ({ tick, bump: () => setTick((n) => n + 1) }), [tick])
  return (
    <SponsorFlybyContext.Provider value={value}>
      {children}
    </SponsorFlybyContext.Provider>
  )
}
