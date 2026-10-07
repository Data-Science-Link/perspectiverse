import { chromium, devices } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:5173/'
const outDir = process.env.OUT_DIR || 'artifacts/screenshots'

async function dismissWelcome(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await welcome.waitFor({ state: 'hidden' })
  }
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(outDir, name), fullPage: true })
}

async function capture(viewport, prefix) {
  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: viewport === 'mobile' ? devices['iPhone 13'].viewport : { width: 1280, height: 800 },
    deviceScaleFactor: viewport === 'mobile' ? 2 : 1,
  })
  const page = await context.newPage()
  await page.addInitScript(() => {
    window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  })

  await page.goto(baseURL)
  await dismissWelcome(page)
  await shot(page, `${prefix}-landing.png`)

  await page.getByRole('button', { name: 'Open menu' }).click()
  await page.locator('.menu-drawer').waitFor({ state: 'visible' })
  await page.waitForTimeout(280)
  await shot(page, `${prefix}-menu-open.png`)
  await page.keyboard.press('Escape')
  await page.locator('.menu-layer').waitFor({ state: 'hidden' })

  await page.getByRole('banner').getByRole('button', { name: 'Email' }).click()
  await page.getByRole('article', { name: 'Weekly email' }).waitFor({ state: 'visible' })
  await shot(page, `${prefix}-email.png`)
  await page.getByRole('banner').getByRole('button', { name: 'Universe' }).click()

  await page.goto(`${baseURL}?page=methodology`)
  await shot(page, `${prefix}-methodology.png`)

  await page.addInitScript(() => {
    window.localStorage.removeItem('perspectiverse.hide-welcome')
  })
  await page.goto(baseURL)
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  await welcome.waitFor({ state: 'visible' })
  await page.waitForTimeout(100)
  await shot(page, `${prefix}-welcome.png`)

  await browser.close()
}

await mkdir(outDir, { recursive: true })
await capture('desktop', 'desktop')
await capture('mobile', 'mobile')
console.log(`saved screenshots to ${outDir}`)
