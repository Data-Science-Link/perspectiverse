import { chromium, devices } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { FREEZE_ORBITS_STORAGE_KEY } from '../src/lib/solarCamera.js'

const port = Number(process.env.PV_PREVIEW_PORT) || 4173
const baseURL = `http://127.0.0.1:${port}`
const outDir = new URL('../docs/evidence/pr-234/', import.meta.url).pathname
const prefix = process.env.PV_EVIDENCE_PREFIX || 'after'

async function startPreview() {
  const child = spawn('npm', ['run', 'preview', '--', '--host', '127.0.0.1', '--port', String(port)], {
    cwd: process.cwd(),
    stdio: 'ignore',
  })
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const res = await fetch(baseURL)
      if (res.ok) return child
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  child.kill()
  throw new Error('preview server did not start')
}

async function waitForCamera(page) {
  for (let i = 0; i < 80; i += 1) {
    const ok = await page.evaluate(() => Boolean(window.__PV_SOLAR_CAMERA__?.read?.()))
    if (ok) return
    await page.waitForTimeout(200)
  }
  throw new Error('camera hooks not ready')
}

async function readCamera(page) {
  return page.evaluate(() => {
    const view = window.__PV_SOLAR_CAMERA__?.read?.()
    if (!view) return null
    return {
      distance: view.distance,
      position: [...view.position],
      target: [...view.target],
    }
  })
}

function fmtPose(view) {
  if (!view) return null
  const p = view.position.map((v) => v.toFixed(2)).join(', ')
  const t = view.target.map((v) => v.toFixed(2)).join(', ')
  return {
    distance: Number(view.distance.toFixed(2)),
    position: p,
    target: t,
    raw: view,
  }
}

async function setCaption(page, title, view) {
  const pose = fmtPose(view)
  const text = pose
    ? `${title} — d ${pose.distance} pos [${pose.position}] tgt [${pose.target}]`
    : title
  await page.evaluate((caption) => {
    let el = document.getElementById('pv-evidence-caption')
    if (!el) {
      el = document.createElement('div')
      el.id = 'pv-evidence-caption'
      el.style.cssText =
        'position:fixed;bottom:14px;left:14px;z-index:99999;background:rgba(5,6,11,0.88);color:#f4f2ff;padding:10px 14px;font:600 13px/1.35 \"Instrument Sans\",Segoe UI,sans-serif;border:1px solid rgba(255,255,255,0.18);border-radius:8px;pointer-events:none;max-width:92vw'
      document.body.appendChild(el)
    }
    el.textContent = caption
  }, text)
}

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await welcome.waitFor({ state: 'hidden' })
  }
}

async function zoomAndPan(page) {
  for (let step = 0; step < 6; step += 1) {
    await page.evaluate(() => window.__PV_SOLAR_CAMERA__?.dolly?.(0.55))
    await page.waitForTimeout(140)
  }
  await page.evaluate(() => window.__PV_SOLAR_CAMERA__?.truck?.(4, 2))
  await page.waitForTimeout(500)
}

async function captureSet(page, labelPrefix, mobile) {
  await page.waitForTimeout(1000)
  const before = await readCamera(page)
  await setCaption(page, `${labelPrefix} 1 — zoomed + panned (before planet)`, before)
  await page.screenshot({ path: `${outDir}/${labelPrefix}-1-home.png` })

  if (mobile) {
    await page.locator('.observatory .planet-label').first().click({ force: true })
  } else {
    await page.getByRole('button', { name: 'Perspectives' }).click()
  }
  await page.waitForURL(/topic=/)
  await page.waitForTimeout(700)
  await page.screenshot({ path: `${outDir}/${labelPrefix}-2-planet.png` })

  if (mobile) {
    await page.locator('button.chrome-back').click()
  } else {
    await page.getByRole('button', { name: '← All topics' }).click()
  }
  await page.waitForURL((url) => !url.search.includes('topic='))
  await waitForCamera(page)
  await page.waitForTimeout(1100)

  const after = await readCamera(page)
  await setCaption(page, `${labelPrefix} 3 — after back (should match step 1)`, after)
  await page.screenshot({ path: `${outDir}/${labelPrefix}-3-back.png` })

  return { before, after }
}

const externalPreview = process.env.PV_EXTERNAL_PREVIEW === '1'
const preview = externalPreview ? null : await startPreview()
await mkdir(outDir, { recursive: true })

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist'],
})

const initScript = () => {
  window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  window.localStorage.setItem(FREEZE_ORBITS_STORAGE_KEY, '1')
}

const only = process.env.PV_ONLY || 'both'
const report = { prefix, port, only, poses: {} }

if (only === 'both' || only === 'desktop') {
  const desktopPage = await browser.newPage({
    ...devices['Desktop Chrome'],
    viewport: { width: 1280, height: 800 },
  })
  await desktopPage.addInitScript(initScript)
  await desktopPage.goto(baseURL)
  await enterSolarSystem(desktopPage)
  await waitForCamera(desktopPage)
  await zoomAndPan(desktopPage)
  const desktop = await captureSet(desktopPage, `${prefix}-desktop`, false)
  report.poses.desktop = { before: fmtPose(desktop.before), after: fmtPose(desktop.after) }
}

if (only === 'both' || only === 'phone') {
  const mobilePage = await browser.newPage({
    ...devices['Pixel 7'],
    viewport: { width: 390, height: 844 },
  })
  await mobilePage.addInitScript(initScript)
  await mobilePage.goto(baseURL)
  await enterSolarSystem(mobilePage)
  await waitForCamera(mobilePage)
  await zoomAndPan(mobilePage)
  const mobile = await captureSet(mobilePage, `${prefix}-phone`, true)
  report.poses.phone = { before: fmtPose(mobile.before), after: fmtPose(mobile.after) }
}

await browser.close()
preview?.kill()

await writeFile(`${outDir}/${prefix}-poses.json`, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
