/**
 * Capture PR #233 evidence (screenshots + phone webm + frame timing).
 * Usage: npm run build && npm run preview -- --host 127.0.0.1 --port 4173 &
 *        node scripts/capture_pr233_evidence.mjs [--base-url http://127.0.0.1:4173] [--out docs/evidence/pr-233]
 */
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium, devices } from '@playwright/test'

const baseURL = process.argv.includes('--base-url')
  ? process.argv[process.argv.indexOf('--base-url') + 1]
  : 'http://127.0.0.1:4173'
const outRoot = process.argv.includes('--out')
  ? process.argv[process.argv.indexOf('--out') + 1]
  : 'docs/evidence/pr-233'

const screenshotDir = path.join(outRoot, 'screenshots')
const videoDir = path.join(outRoot, 'video')

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await welcome.waitFor({ state: 'hidden', timeout: 15_000 }).catch(() => {})
  }
}

async function waitFlybyVisible(page) {
  await enterSolarSystem(page)
  await page.waitForFunction(() => {
    const el = document.querySelector('.sponsor-flyby-screen')
    return el?.style.visibility === 'visible'
  }, { timeout: 45_000 })
}

async function captureScreenshot(page, filePath) {
  await page.goto(`${baseURL}/?sponsorFlyby=1&sponsorProgress=0.5`)
  await enterSolarSystem(page)
  await waitFlybyVisible(page)
  await page.waitForTimeout(400)
  await page.screenshot({ path: filePath, fullPage: false })
}

function frameStats(deltasMs) {
  const sorted = [...deltasMs].filter((d) => d > 0 && d < 500).sort((a, b) => a - b)
  if (!sorted.length) {
    return { samples: 0, p50: null, p95: null, max: null }
  }
  const p50 = sorted[Math.floor(sorted.length * 0.5)]
  const p95 = sorted[Math.floor(sorted.length * 0.95)]
  return {
    samples: sorted.length,
    p50: Math.round(p50 * 100) / 100,
    p95: Math.round(p95 * 100) / 100,
    max: Math.round(sorted[sorted.length - 1] * 100) / 100,
  }
}

async function measureFrames(page, { flyby }) {
  await page.addInitScript(() => {
    window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  })
  if (!flyby) {
    await page.emulateMedia({ reducedMotion: 'reduce' })
  }
  const url = flyby
    ? `${baseURL}/?sponsorFlyby=1&sponsorProgress=0.5`
    : `${baseURL}/`
  await page.goto(url)
  await enterSolarSystem(page)
  if (flyby) {
    await waitFlybyVisible(page)
  } else {
    await page.waitForSelector('.observatory canvas', { timeout: 20_000 })
    await page.waitForTimeout(1200)
  }
  const deltas = await page.evaluate(async () => {
    await new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(resolve))
    })
    return new Promise((resolve) => {
      const deltas = []
      let last = performance.now()
      let n = 0
      const tick = (now) => {
        deltas.push(now - last)
        last = now
        n += 1
        if (n < 300) requestAnimationFrame(tick)
        else resolve(deltas)
      }
      requestAnimationFrame(tick)
    })
  })
  return frameStats(deltas)
}

async function recordPhoneWebm(browser, filePath) {
  const { readdir, rename } = await import('node:fs/promises')
  const context = await browser.newContext({
    ...devices['Pixel 7'],
    viewport: { width: 390, height: 844 },
    recordVideo: { dir: path.dirname(filePath), size: { width: 390, height: 844 } },
  })
  const page = await context.newPage()
  await page.addInitScript(() => localStorage.setItem('perspectiverse.hide-welcome', '1'))
  await page.goto(`${baseURL}/?sponsorFlyby=animate`)
  await waitFlybyVisible(page)
  await page.waitForTimeout(4500)
  await context.close()
  const name = (await readdir(path.dirname(filePath))).find((f) => f.endsWith('.webm'))
  if (name) {
    await rename(path.join(path.dirname(filePath), name), filePath)
  }
}

async function main() {
  await mkdir(screenshotDir, { recursive: true })
  await mkdir(videoDir, { recursive: true })

  const browser = await chromium.launch({
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist'],
  })

  async function openLinear(page) {
    await page.goto(`${baseURL}/?sponsorFlyby=1&sponsorProgress=0.5`)
    await page.waitForFunction(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    }, { timeout: 25_000 })
    await page.getByRole('button', { name: 'Linear' }).click()
    await page.waitForFunction(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    }, { timeout: 25_000 })
    await page.waitForTimeout(400)
  }

  for (const [name, viewport] of [
    ['desktop', { width: 1280, height: 800 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    const page = await browser.newPage({ viewport })
    await page.addInitScript(() => localStorage.setItem('perspectiverse.hide-welcome', '1'))
    await captureScreenshot(page, path.join(screenshotDir, `${name}-orbits-sponsor-1.png`))
    await openLinear(page)
    await page.screenshot({
      path: path.join(screenshotDir, `${name}-linear-sponsor-1.png`),
      fullPage: false,
    })
    await page.close()
  }

  const phone = await browser.newPage({
    ...devices['Pixel 7'],
    viewport: { width: 390, height: 844 },
  })
  const session = await phone.context().newCDPSession(phone)
  await session.send('Emulation.setCPUThrottlingRate', { rate: 4 })

  const withoutFlyby = await measureFrames(phone, { flyby: false })
  const withFlyby = await measureFrames(phone, { flyby: true })

  await writeFile(
    path.join(outRoot, 'frame-timing-phone-4x-cpu.json'),
    JSON.stringify({
      viewport: { width: 390, height: 844 },
      cpuThrottleRate: 4,
      withoutFlybyAnimate: withoutFlyby,
      withFlybyAnimate: withFlyby,
      capturedAt: new Date().toISOString(),
    }, null, 2),
  )

  await phone.close()
  await recordPhoneWebm(browser, path.join(videoDir, 'flyby-phone-390x844.webm'))
  await browser.close()

  console.log('pr233 evidence captured under', outRoot)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
