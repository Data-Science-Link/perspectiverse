export function skySettings(isMobile) {
  if (isMobile) {
    return {
      dpr: 1,
      antialias: false,
      bloom: false,
      dreiStars: 0,
      twinkleStars: 220,
      textureQuality: 'low',
      sphereDetail: [32, 24],
      ringSegments: 96,
      haloDetail: [24, 24],
      powerPreference: 'low-power',
    }
  }
  return {
    dpr: [1, 1.5],
    antialias: true,
    bloom: true,
    dreiStars: 2800,
    twinkleStars: 320,
    textureQuality: 'high',
    sphereDetail: [48, 36],
    ringSegments: 128,
    haloDetail: [32, 32],
    powerPreference: 'high-performance',
  }
}
