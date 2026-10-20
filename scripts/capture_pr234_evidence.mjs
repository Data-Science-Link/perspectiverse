import { chromium, devices } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { FREEZE_ORBITS_STORAGE_KEY } from '../src/lib/solarCamera.js'

const port = 4173
const baseURL = `http://127.0.0.1:${port}`
const outDir = '/opt/cursor/artifacts/screenshots'

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

async function readDistance(page) {
  return page.evaluate(() => window.__PV_SOLAR_CAMERA__?.read?.()?.distance ?? null)
}

async function setCaption(page, title, distance) {
  const text = `${title} — camera distance: ${Number(distance).toFixed(2)}`
  await page.evaluate((caption) => {
    let el = document.getElementById('pv-evidence-caption')
    if (!el) {
      el = document.createElement('div')
      el.id = 'pv-evidence-caption'
      el.style.cssText =
        'position:fixed;bottom:14px;left:14px;z-index:99999;background:rgba(5,6,11,0.88);color:#f4f2ff;padding:10px 14px;font:600 15px/1.35 \"Instrument Sans\",Segoe UI,sans-serif;border:1px solid rgba(255,255,255,0.18);border-radius:8px;pointer-events:none'
      document.body.appendChild(el)
    }
    el.textContent = caption
  }, text)
}

async function zoomToDistance(page, target = 30, tolerance = 0.45) {
  for (let step = 0; step < 48; step += 1) {
    const distance = await readDistance(page)
    if (distance != null && distance <= target + tolerance) return distance
    await page.evaluate(() => window.__PV_SOLAR_CAMERA__?.dolly?.(1.15))
    await page.waitForTimeout(160)
  }
  return readDistance(page)
}

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await welcome.waitFor({ state: 'hidden' })
  }
}

async function captureSet(page, prefix, mobile) {
  await page.waitForTimeout(1200)
  const homeDistance = await readDistance(page)
  await setCaption(page, `${mobile ? 'Mobile' : 'Desktop'} 1 — Home view`, homeDistance)
  await page.screenshot({ path: `${outDir}/${prefix}-1-home.png` })

  const zoomedDistance = await zoomToDistance(page, 30)
  await page.waitForTimeout(500)
  const zoomedRead = await readDistance(page)
  await setCaption(page, `${mobile ? 'Mobile' : 'Desktop'} 2 — Zoomed before planet`, zoomedRead ?? zoomedDistance)
  await page.screenshot({ path: `${outDir}/${prefix}-2-zoomed.png` })

  if (mobile) {
    await page.locator('.observatory .planet-label').first().click({ force: true })
  } else {
    await page.getByRole('button', { name: 'Perspectives' }).click()
  }
  await page.waitForURL(/topic=/)
  await page.waitForTimeout(700)

  if (mobile) {
    await page.locator('button.chrome-back').click()
  } else {
    await page.getByRole('button', { name: '← All topics' }).click()
  }
  await page.waitForURL((url) => !url.search.includes('topic='))
  await waitForCamera(page)
  await page.waitForTimeout(1100)

  const restored = await readDistance(page)
  await setCaption(page, `${mobile ? 'Mobile' : 'Desktop'} 3 — After planet exit`, restored)
  await page.screenshot({ path: `${outDir}/${prefix}-3-restored.png` })

  return { homeDistance, zoomedRead, restored }
}

const preview = await startPreview()
await mkdir(outDir, { recursive: true })

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist'],
})

const initScript = () => {
  window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  window.localStorage.setItem(FREEZE_ORBITS_STORAGE_KEY, '1')
}

const desktopPage = await browser.newPage({
  ...devices['Desktop Chrome'],
  viewport: { width: 1280, height: 800 },
})
await desktopPage.addInitScript(initScript)
await desktopPage.goto(baseURL)
await enterSolarSystem(desktopPage)
await waitForCamera(desktopPage)
const desktop = await captureSet(desktopPage, 'camera-evidence-desktop', false)

const mobilePage = await browser.newPage({
  ...devices['Pixel 7'],
  viewport: { width: 390, height: 844 },
})
await mobilePage.addInitScript(initScript)
await mobilePage.goto(baseURL)
await enterSolarSystem(mobilePage)
await waitForCamera(mobilePage)
const mobile = await captureSet(mobilePage, 'camera-evidence-mobile', true)

await browser.close()
preview.kill()

console.log(JSON.stringify({ desktop, mobile }, null, 2))
