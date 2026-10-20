import { chromium, devices } from '@playwright/test'
import path from 'node:path'
import { readFile } from 'node:fs/promises'

const outDir = path.join('docs/evidence/pr-265')
const baseURL = process.env.BASE_URL || 'http://127.0.0.1:4173/'
const pendingUrl = `${baseURL}?category=Education&topic=Education-4`

const LABEL_HELD_PLANET = {
  id: 'Education-4',
  name: 'Pending',
  category: 'Education',
  total_volume_percent: 18.5,
  post_count: 4,
  stance_check: 'label held',
  summary: 'Topic label not ready for this edition.',
  brief: 'Topic label not ready for this edition.',
  detail:
    'Topic label not ready for this edition.\n\nThe offline label guard held this planet until a readable label is available.\n\nReaders should not see placeholder or garbage copy here.',
  perspectives: [
    {
      id: 'Education-4A',
      title: 'Pending',
      summary: 'Topic label not ready for this edition.',
      volume_percent: 100,
      post_count: 4,
      arguments: [
        'The posts in this sample share one bar-and-neighborhood thread.',
        'A readable face title was not ready at finalize.',
      ],
      representative_posts: [
        {
          author: 'earthbenderjim.bsky.social',
          text: "There's a nice little spot near me that is in an old house and it's the perfect spot to read at.",
          likes: 9,
        },
        {
          author: 'highway62.bsky.social',
          text: 'If you are in the neighborhood, you should totally stop at the bar there.',
          likes: 2,
        },
      ],
      top_terms: ['bar', 'neighborhood', 'read', 'spot'],
    },
  ],
  face_distinctness: 0,
}

async function patchedDataJson() {
  const raw = await readFile(new URL('../public/data.json', import.meta.url), 'utf8')
  const payload = JSON.parse(raw)
  payload.sections = payload.sections || {}
  payload.sections.Education = [LABEL_HELD_PLANET]
  return payload
}

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
  const payload = await patchedDataJson()
  const context = await browser.newContext({
    viewport: viewport === 'mobile' ? devices['Pixel 7'].viewport : { width: 1280, height: 800 },
    deviceScaleFactor: viewport === 'mobile' ? 2 : 1,
  })
  const page = await context.newPage()
  page.setDefaultTimeout(60_000)
  await page.route('**/data.json', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    })
  })
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
