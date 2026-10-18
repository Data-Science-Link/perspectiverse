import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const screenshotDir = path.join(__dirname, 'artifacts', 'linear-grid')

async function enterSolarSystem(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  })
  await page.goto('/')
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()
  }
}

async function openLinearGrid(page) {
  await enterSolarSystem(page)
  await page.getByRole('button', { name: 'Linear' }).click()
  await expect(page.getByRole('button', { name: 'Orbits' })).toBeVisible()
  await expect.poll(async () => page.locator('.observatory .planet-label').count()).toBeGreaterThanOrEqual(10)
  await page.waitForTimeout(1200)
}

async function glyphHeight(label) {
  return label.evaluate((node) => {
    const range = document.createRange()
    range.selectNodeContents(node)
    return range.getBoundingClientRect().height
  })
}

async function labelLayout(page) {
  const labels = page.locator('.observatory .planet-label')
  const count = await labels.count()
  const entries = []
  for (let index = 0; index < count; index += 1) {
    const label = labels.nth(index)
    const name = (await label.innerText()).trim()
    const box = await label.boundingBox()
    const glyph = await glyphHeight(label)
    const topicIndex = Number(await label.getAttribute('data-topic-index'))
    entries.push({ index, topicIndex, name, box, glyph })
  }
  return entries.sort((a, b) => a.topicIndex - b.topicIndex)
}

function rectanglesOverlap(a, b, margin = 1) {
  return (
    a.x < b.x + b.width - margin
    && a.x + a.width > b.x + margin
    && a.y < b.y + b.height - margin
    && a.y + a.height > b.y + margin
  )
}

function expectNoLabelOverlaps(entries) {
  for (let i = 0; i < entries.length; i += 1) {
    for (let j = i + 1; j < entries.length; j += 1) {
      expect(rectanglesOverlap(entries[i].box, entries[j].box)).toBe(false)
    }
  }
}

async function expectLayoutBookOrder(page, mode = 'grid') {
  const layout = await page.evaluate(() => window.__perspectiverseLinearLayout)
  expect(layout?.mode).toBe(mode)
  const { positions, cols } = layout
  expect(positions.length).toBeGreaterThanOrEqual(10)
  for (let index = 1; index < positions.length; index += 1) {
    const prev = positions[index - 1]
    const next = positions[index]
    const prevRow = Math.floor((index - 1) / cols)
    const nextRow = Math.floor(index / cols)
    if (prevRow === nextRow) {
      expect(next[0]).toBeGreaterThan(prev[0])
      expect(Math.abs(next[1] - prev[1])).toBeLessThan(0.25)
    } else {
      expect(next[1]).toBeLessThan(prev[1])
      expect(next[0]).toBeLessThan(prev[0])
    }
  }
}

function entriesReady(entries) {
  if (entries.length < 10) return false
  for (const entry of entries) {
    if (!entry.box || entry.glyph < 14) return false
  }
  for (let i = 0; i < entries.length; i += 1) {
    for (let j = i + 1; j < entries.length; j += 1) {
      if (rectanglesOverlap(entries[i].box, entries[j].box)) return false
    }
  }
  return true
}

async function expectAllPlanetsVisible(page) {
  await expect.poll(async () => entriesReady(await labelLayout(page)), { timeout: 15_000 }).toBe(true)
  const entries = await labelLayout(page)
  expect(entries.length).toBeGreaterThanOrEqual(10)
  expectNoLabelOverlaps(entries)
  const canvas = await page.locator('.observatory canvas').boundingBox()
  expect(canvas).not.toBeNull()
  for (const entry of entries) {
    expect(entry.box.x).toBeGreaterThanOrEqual(canvas.x - 2)
    expect(entry.box.y).toBeGreaterThanOrEqual(canvas.y - 2)
    expect(entry.box.x + entry.box.width).toBeLessThanOrEqual(canvas.x + canvas.width + 2)
    expect(entry.box.y + entry.box.height).toBeLessThanOrEqual(canvas.y + canvas.height + 2)
  }
  return entries
}

async function expectLabelsInsideCanvas(page) {
  const canvasBox = await page.locator('.observatory canvas').boundingBox()
  expect(canvasBox).not.toBeNull()
  const entries = await labelLayout(page)
  for (const entry of entries) {
    expect(entry.box.x).toBeGreaterThanOrEqual(canvasBox.x - 1)
    expect(entry.box.y).toBeGreaterThanOrEqual(canvasBox.y - 1)
    expect(entry.box.x + entry.box.width).toBeLessThanOrEqual(canvasBox.x + canvasBox.width + 1)
    expect(entry.box.y + entry.box.height).toBeLessThanOrEqual(canvasBox.y + canvasBox.height + 1)
  }
  const gaza = entries.find((entry) => entry.topicIndex === 0)
  expect(gaza).toBeTruthy()
  expect(gaza.box.x).toBeGreaterThanOrEqual(canvasBox.x)
}

test.describe('Linear grid on phones', () => {
  test.use({ deviceScaleFactor: 1 })

  test('portrait shows every planet in reading order', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', 'phone portrait layout')
    await page.setViewportSize({ width: 390, height: 844 })
    await openLinearGrid(page)
    const entries = await expectAllPlanetsVisible(page)
    await expectLayoutBookOrder(page, 'grid')
    await page.screenshot({ path: path.join(screenshotDir, 'phone-portrait.png'), fullPage: false })
    await page.locator('.observatory .planet-label').filter({ hasText: entries[1].name }).click()
    await expect(page.getByRole('button', { name: 'Read more …' })).toBeVisible()
  })

  test('landscape shows every planet in reading order', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', 'phone landscape layout')
    await page.setViewportSize({ width: 844, height: 390 })
    await openLinearGrid(page)
    await expectAllPlanetsVisible(page)
    await expectLayoutBookOrder(page, 'grid')
    await page.screenshot({ path: path.join(screenshotDir, 'phone-landscape.png'), fullPage: false })
  })
})

test.describe('Linear layout on desktop', () => {
  test('keeps labels inside the canvas and captures a screenshot', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'desktop layout')
    await openLinearGrid(page)
    await expect.poll(async () => {
      const canvas = await page.locator('.observatory canvas').boundingBox()
      return canvas && canvas.width > 400
    }).toBeTruthy()
    await expectLayoutBookOrder(page, 'linear')
    await expectLabelsInsideCanvas(page)
    await page.screenshot({ path: path.join(screenshotDir, 'desktop.png'), fullPage: false })
  })
})
