import { expect, test } from '@playwright/test'

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()
  }
}

function glyphHeight(page) {
  return page.locator('.sponsor-flyby-banner-text').evaluate((node) => {
    const rect = node.getBoundingClientRect()
    return rect.height
  })
}

test.describe('Sponsor flyby placeholder', () => {
  test('screen-space banner is legible, in view, and click-through', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=1')
    await enterSolarSystem(page)

    const text = page.locator('.sponsor-flyby-banner-text')
    await expect.poll(async () => page.locator('[data-sponsor-flyby="visible"]').count()).toBeGreaterThan(0)
    await expect(text).toHaveText('Does Advertising Work? Just Did!')

    await expect.poll(async () => glyphHeight(page), { timeout: 15_000 }).toBeGreaterThanOrEqual(14)

    const inView = await text.evaluate((node) => {
      const rect = node.getBoundingClientRect()
      const vw = window.innerWidth
      const vh = window.innerHeight
      return rect.left >= 0
        && rect.top >= 0
        && rect.right <= vw
        && rect.bottom <= vh
        && rect.width > 0
    })
    expect(inView).toBe(true)

    const label = page.locator('.observatory .planet-label').first()
    await expect(label).toBeVisible()
    const labelBox = await label.boundingBox()
    expect(labelBox).toBeTruthy()
    await page.mouse.click(labelBox.x + labelBox.width / 2, labelBox.y + labelBox.height / 2)
    await expect(page.getByRole('button', { name: 'Read more …' })).toBeVisible()

    if (testInfo.project.name === 'desktop') {
      await expect(page.locator('[data-sponsor-flyby="visible"]')).toHaveCount(0)
    }
  })

  test('banner does not capture pointer hits', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=1')
    await enterSolarSystem(page)
    await expect.poll(async () => page.locator('[data-sponsor-flyby="visible"]').count()).toBeGreaterThan(0)

    const hit = await page.locator('.sponsor-flyby-banner-text').evaluate((node) => {
      const rect = node.getBoundingClientRect()
      const x = rect.left + rect.width / 2
      const y = rect.top + rect.height / 2
      const target = document.elementFromPoint(x, y)
      return {
        tag: target?.tagName,
        isBanner: target?.closest?.('.sponsor-flyby-screen') != null,
      }
    })
    expect(hit.isBanner).toBe(false)
  })
})
