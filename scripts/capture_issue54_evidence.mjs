import { chromium, devices } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:4173/'
const outDir = process.env.OUT_DIR || '/opt/cursor/artifacts/screenshots'
const faceURL = `${baseURL}?topic=2&face=2A`

const launchArgs = [
  '--use-gl=angle',
  '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader',
  '--ignore-gpu-blocklist',
]

async function dismissWelcome(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await welcome.waitFor({ state: 'hidden' })
  }
}

async function waitForCanvas(page) {
  const canvas = page.locator('.observatory canvas')
  await canvas.waitFor({ state: 'visible', timeout: 20_000 })
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const lit = await canvas.evaluate((node) => {
    const width = node.width
    const height = node.height
    const gl = node.getContext('webgl2') || node.getContext('webgl')
    if (!gl || width < 8 || height < 8) return 0
    const sampleW = Math.min(64, width)
    const sampleH = Math.min(64, height)
    const pixels = new Uint8Array(sampleW * sampleH * 4)
    gl.readPixels(0, 0, sampleW, sampleH, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
    let count = 0
    for (let i = 0; i < pixels.length; i += 4) {
      if (pixels[i] + pixels[i + 1] + pixels[i + 2] > 40) count += 1
    }
      return count
    })
    if (lit >= 8) return
    await page.waitForTimeout(250)
  }
  console.warn('WebGL canvas may be blank (swiftshader); continuing anyway.')
}

function postRoot(page) {
  return page.locator('.reading-sheet-posts, .reading-posts').first()
}

async function prepareCollapsedPosts(page, viewport) {
  const root = postRoot(page)
  await root.waitFor({ state: 'visible' })
  const scroller = root.locator('.post-scroller').first()
  const scrollHost = (await scroller.count()) ? scroller : root
  const cards = root.locator('.post-card')
  await cards.nth(4).waitFor({ state: 'visible' })
  const more = root.getByRole('button', { name: /more posts/ })
  await more.waitFor({ state: 'visible' })
  await scrollHost.evaluate((el) => {
    el.scrollTop = 0
  })
  await page.waitForTimeout(150)
}

async function prepareExpandedPosts(page, viewport) {
  const root = postRoot(page)
  const scroller = root.locator('.post-scroller').first()
  const scrollHost = (await scroller.count()) ? scroller : root
  const cards = root.locator('.post-card')
  await cards.nth(10).waitFor({ state: 'visible' })
  const fewer = root.getByRole('button', { name: 'Show fewer posts' })
  await fewer.waitFor({ state: 'visible' })
  await scrollHost.evaluate((el, wide) => {
    const fewerBtn = el.querySelector('.post-expand')
    const cards = el.querySelectorAll('.post-card')
    if (!fewerBtn) return
    if (wide) {
      el.scrollTop = el.scrollHeight
      return
    }
    if (cards[4]) cards[4].scrollIntoView({ block: 'start' })
    fewerBtn.scrollIntoView({ block: 'end' })
  }, viewport.width >= 500)
  await page.waitForTimeout(150)
}

async function captureVariant(page, prefix, viewport, { desktopCanvas }) {
  await page.setViewportSize(viewport)
  await page.addInitScript(() => {
    window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  })
  await page.goto(faceURL)
  await dismissWelcome(page)
  if (desktopCanvas) await waitForCanvas(page)
  await page.locator('.top-terms').first().waitFor({ state: 'visible' })
  await page.getByRole('heading', { level: 1 }).first().waitFor({ state: 'visible' })

  if (viewport.width < 500) {
    await page.getByRole('button', { name: 'See all posts' }).click()
    await page.locator('.reading-sheet-posts').waitFor({ state: 'visible' })
  } else {
    await page.evaluate(() => {
      const chart = document.querySelector('.reading-band:first-child')
      const copy = document.querySelector('.reading-band.reading-copy')
      if (chart) chart.style.display = 'none'
      if (copy) copy.style.display = 'none'
      const body = document.querySelector('.reading-body')
      if (body) body.style.gridTemplateRows = '1fr'
    })
  }

  await prepareCollapsedPosts(page, viewport)
  await page.screenshot({
    path: path.join(outDir, `${prefix}-collapsed.png`),
    fullPage: false,
  })

  await postRoot(page).getByRole('button', { name: /more posts/ }).click()
  await postRoot(page).getByRole('button', { name: 'Show fewer posts' }).waitFor({ state: 'visible' })
  await prepareExpandedPosts(page, viewport)
  await postRoot(page).getByRole('button', { name: 'Show fewer posts' }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(150)
  await page.screenshot({
    path: path.join(outDir, `${prefix}-expanded.png`),
    fullPage: false,
  })
}

await mkdir(outDir, { recursive: true })
const browser = await chromium.launch({ args: launchArgs })
const page = await browser.newPage()

await captureVariant(page, 'issue54-desktop-1280x800', { width: 1280, height: 800 }, { desktopCanvas: true })
await captureVariant(page, 'issue54-mobile-390x844', { width: 390, height: 844 }, { desktopCanvas: false })

await browser.close()
console.log(`saved issue #54 evidence to ${outDir}`)
