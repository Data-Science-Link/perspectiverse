import { Vector3 } from 'three'

/** @typedef {{ position: [number, number, number], target: [number, number, number], distance: number }} SolarView */

const _pos = new Vector3()
const _target = new Vector3()

/** @type {SolarView | null} */
let _solarView = null

export function readCameraLookAt(controls) {
  if (!controls?.getPosition || !controls.getTarget) return null
  controls.getPosition(_pos, true)
  controls.getTarget(_target, true)
  return {
    position: [_pos.x, _pos.y, _pos.z],
    target: [_target.x, _target.y, _target.z],
    distance: _pos.distanceTo(_target),
  }
}

export function stashSolarView(controls) {
  const snapshot = readCameraLookAt(controls)
  if (snapshot) _solarView = snapshot
  return snapshot
}

export function peekSolarView() {
  return _solarView
}

export function clearSolarView() {
  _solarView = null
}

export function applySolarView(controls, view, transition = false) {
  if (!controls || !view?.position || !view?.target) return false
  const [px, py, pz] = view.position
  const [tx, ty, tz] = view.target
  controls.setLookAt(px, py, pz, tx, ty, tz, transition)
  return true
}

export function restoreSolarView(controls, transition = false) {
  if (!_solarView) return false
  return applySolarView(controls, _solarView, transition)
}

export function installSolarCameraTestHooks(getControls) {
  if (typeof window === 'undefined') return
  window.__PV_SOLAR_CAMERA__ = {
    read: () => readCameraLookAt(getControls()),
    peekStash: () => peekSolarView(),
    stash: () => stashSolarView(getControls()),
    dolly: (amount = 0.45) => {
      const controls = getControls()
      if (controls?.dolly) controls.dolly(amount, true)
    },
  }
}
