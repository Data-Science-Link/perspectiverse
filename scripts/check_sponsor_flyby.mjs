import assert from 'node:assert/strict'
import { pillOpacityForLabels, towSideForShip } from '../src/lib/sponsorFlybyPlacement.js'
import { sponsorFlightPath, sponsorFlightPathLinear } from '../src/lib/sponsorFlybyPath.js'

const bounds = { left: 10, right: 300, top: 50, bottom: 400 }
assert.equal(towSideForShip(50, 120, bounds), 'right')
assert.equal(towSideForShip(250, 120, bounds), 'left')
assert.equal(towSideForShip(150, 120, bounds, 'left'), 'left')

const noOverlapOpacity = pillOpacityForLabels(
  { left: 10, right: 100, top: 10, bottom: 40 },
  [{ left: 200, right: 260, top: 200, bottom: 230 }],
)
assert.equal(noOverlapOpacity, 1)

const overlapOpacity = pillOpacityForLabels(
  { left: 10, right: 100, top: 10, bottom: 40 },
  [{ left: 50, right: 120, top: 20, bottom: 35 }],
)
assert.equal(overlapOpacity, 0.22)

const linearStart = sponsorFlightPathLinear(0, 12, 5)
const linearEnd = sponsorFlightPathLinear(1, 12, 5)
assert.ok(linearEnd.x > linearStart.x)
assert.ok(Math.abs(linearStart.z) < 4)

const orbitMid = sponsorFlightPath(0.5)
assert.ok(orbitMid.z > 10)

console.log('check_sponsor_flyby: ok')
