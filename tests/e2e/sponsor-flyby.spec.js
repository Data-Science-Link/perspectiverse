import { expect, test } from '@playwright/test'

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()
  }
}

test.describe('Sponsor flyby placeholder', () => {
  test('banner is visible in test loop without blocking planet clicks', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=1')
    await enterSolarSystem(page)

    const banner = page.locator('.sponsor-flyby-banner')
    await expect.poll(async () => banner.isVisible()).toBe(true)
    await expect(banner).toHaveText('Does Advertising Work? Just Did!')

    if (testInfo.project.name === 'mobile') {
      await page.locator('.observatory .planet-label').first().click({ force: true })
    } else {
      await page.locator('.observatory .planet-label').first().click({ force: true })
    }
    await expect(page.getByRole('button', { name: 'Read more …' })).toBeVisible()
  })
})
