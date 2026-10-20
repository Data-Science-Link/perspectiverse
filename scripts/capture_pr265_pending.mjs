import { chromium, devices } from '@playwright/test'
import path from 'node:path'

const outDir = path.join('docs/evidence/pr-265')
const baseURL = process.env.BASE_URL || 'http://127.0.0.1:4173/'
const pendingUrl = `${baseURL}?category=Education&topic=Education-4`

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await welcome.waitFor({ state: 'hidden' })
  }
}

async function capture(viewport) {
  const suffix = viewport === 'mobile' ? 'phone' : 'desktop'
  const browser = await chromium.launch({
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist'],
  })
  const context = await browser.newContext({
    viewport: viewport === 'mobile' ? devices['Pixel 7'].viewport : { width: 1280, height: 800 },
    deviceScaleFactor: viewport === 'mobile' ? 2 : 1,
  })
  const page = await context.newPage()
  page.setDefaultTimeout(60_000)
  await page.addInitScript(() => {
    window.localStorage.setItem('perspectiverse.hide-welcome', '1')
  })
  await page.goto(pendingUrl)
  await enterSolarSystem(page)
  await page.locator('.reading-screen h1').filter({ hasText: 'Pending' }).waitFor({ state: 'visible' })
  await expectNoDuplicateAnalyzedLine(page)
  await page.waitForTimeout(500)
  await page.screenshot({
    path: path.join(outDir, `after-${suffix}-pending.png`),
    fullPage: true,
  })
  await browser.close()
}

async function expectNoDuplicateAnalyzedLine(page) {
  const analyzed = await page.locator('.reading-screen').getByText('Perspectives still being analyzed').count()
  if (analyzed > 0) {
    throw new Error('reading screen still shows stance-analyzed copy for a label-held planet')
  }
  const ready = await page.locator('.reading-screen').getByText('Topic label not ready for this edition').count()
  if (ready < 1) {
    throw new Error('expected label-not-ready copy on reading screen')
  }
}

await capture('desktop')
await capture('mobile')
console.log(`saved pending screenshots to ${outDir}`)
