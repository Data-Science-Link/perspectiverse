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
  await expect(page.locator('.observatory .planet-label').first()).toBeVisible()
}

async function labelLayout(page) {
  const labels = page.locator('.observatory .planet-label')
  const count = await labels.count()
  const entries = []
  for (let index = 0; index < count; index += 1) {
    const label = labels.nth(index)
    const name = (await label.innerText()).trim()
    const box = await label.boundingBox()
    const fontSize = await label.evaluate((node) => parseFloat(window.getComputedStyle(node).fontSize))
    const topicIndex = Number(await label.getAttribute('data-topic-index'))
    entries.push({ index, topicIndex, name, box, fontSize })
  }
  return entries.sort((a, b) => a.topicIndex - b.topicIndex)
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

async function expectAllPlanetsVisible(page, viewport) {
  const entries = await labelLayout(page)
  expect(entries.length).toBeGreaterThanOrEqual(10)
  for (const entry of entries) {
    expect(entry.box).not.toBeNull()
    expect(entry.box.width).toBeGreaterThan(0)
    expect(entry.box.height).toBeGreaterThan(0)
    expect(entry.fontSize).toBeGreaterThanOrEqual(14)
    expect(entry.box.x).toBeGreaterThanOrEqual(-2)
    expect(entry.box.y).toBeGreaterThanOrEqual(-2)
    expect(entry.box.x + entry.box.width).toBeLessThanOrEqual(viewport.width + 2)
    expect(entry.box.y + entry.box.height).toBeLessThanOrEqual(viewport.height + 2)
  }
  return entries
}

test.describe('Linear grid on phones', () => {
  test('portrait shows every planet in reading order', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', 'phone portrait layout')
    await page.setViewportSize({ width: 390, height: 844 })
    await openLinearGrid(page)
    const entries = await expectAllPlanetsVisible(page, { width: 390, height: 844 })
    await expectLayoutBookOrder(page, 'grid')
    await page.screenshot({ path: path.join(screenshotDir, 'phone-portrait.png'), fullPage: false })
    await page.locator('.observatory .planet-label').filter({ hasText: entries[3].name }).click({ force: true })
    await expect(page.getByRole('button', { name: 'Read more …' })).toBeVisible()
  })

  test('landscape shows every planet in reading order', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', 'phone landscape layout')
    await page.setViewportSize({ width: 844, height: 390 })
    await openLinearGrid(page)
    const entries = await expectAllPlanetsVisible(page, { width: 844, height: 390 })
    await expectLayoutBookOrder(page, 'grid')
    await page.screenshot({ path: path.join(screenshotDir, 'phone-landscape.png'), fullPage: false })
  })
})

test.describe('Linear layout on desktop', () => {
  test('keeps the horizontal row and captures a screenshot', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'desktop layout')
    await openLinearGrid(page)
    await expectLayoutBookOrder(page, 'linear')
    const entries = await labelLayout(page)
    expect(entries.length).toBeGreaterThanOrEqual(10)
    await page.screenshot({ path: path.join(screenshotDir, 'desktop.png'), fullPage: false })
  })
})
