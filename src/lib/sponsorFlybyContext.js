import { createContext, useContext } from 'react'

export const SponsorFlybyContext = createContext(null)

export function useSponsorFlybyAnchor() {
  const ctx = useContext(SponsorFlybyContext)
  if (!ctx) {
    throw new Error('useSponsorFlybyAnchor must be used within SponsorFlybyProvider')
  }
  return ctx
}
