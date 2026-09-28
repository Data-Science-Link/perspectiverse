import { expect, test } from '@playwright/test'

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()
  }
}

async function observatoryStats(page) {
  return page.locator('.observatory canvas').evaluate((canvas) => {
    const width = canvas.width
    const height = canvas.height
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    if (!gl || width < 8 || height < 8) {
      return { width, height, lit: 0, samples: 0 }
    }
    const sampleW = Math.min(96, width)
    const sampleH = Math.min(96, height)
    const pixels = new Uint8Array(sampleW * sampleH * 4)
    const x = Math.max(0, Math.floor(width / 2 - sampleW / 2))
    const y = Math.max(0, Math.floor(height / 2 - sampleH / 2))
    gl.readPixels(x, y, sampleW, sampleH, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
    let lit = 0
    for (let i = 0; i < pixels.length; i += 4) {
      if (pixels[i] + pixels[i + 1] + pixels[i + 2] > 40) lit += 1
    }
    return { width, height, lit, samples: sampleW * sampleH }
  })
}

test.describe('Perspectiverse views', () => {
  test('loads a living sky with onboarding, tagline, and orbit toggle', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.removeItem('perspectiverse.hide-welcome')
    })
    await page.goto('/')

    const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
    await expect(welcome).toBeVisible()
    await expect(welcome).toContainText('echo chamber')
    await expect(welcome).toContainText('Planet size')
    await expect(welcome).toContainText('majority')
    await expect(welcome.locator('svg')).toHaveCount(2)
    await expect(page.getByLabel("Don't show this again")).toBeVisible()
    await page.getByLabel("Don't show this again").check()
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()

    await expect(page.getByRole('banner').getByText('See every perspective — and where yours stands.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Show orbit lines' })).toBeVisible()
    await expect(page.locator('.observatory canvas')).toBeVisible()
    await expect(page.getByText('Test your take')).toHaveCount(0)
    await expect(page.getByText('Anti-echo')).toHaveCount(0)
    await expect(page.locator('.pv-graphic')).toHaveCount(0)
    await expect(page.getByText('Filter topics', { exact: true }).first()).toBeVisible()

    await expect.poll(async () => {
      const stats = await observatoryStats(page)
      return stats.width > 64 && stats.height > 64 && stats.lit > 8
    }, { timeout: 20_000 }).toBeTruthy()

    await page.getByRole('button', { name: 'Show orbit lines' }).click()
    await expect(page.getByRole('button', { name: 'Hide orbit lines' })).toBeVisible()

    if (testInfo.project.name === 'mobile') {
      await expect(page.getByLabel('Choose which topics fill the solar system')).toBeVisible()
      await expect(page.getByText(/Drag the sky to look around/)).toBeVisible()
    } else {
      await expect(page.getByRole('heading', { name: 'Perspectiverse' })).toBeVisible()
      await expect(page.getByText(/Bigger planets got more/)).toBeVisible()
    }
  })

  test('respects do not show again and still lets the menu reopen welcome', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/')
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toHaveCount(0)
    await enterSolarSystem(page)
    await page.getByRole('button', { name: 'Open menu' }).click()
    await page.getByRole('button', { name: 'Show the welcome tour' }).click()
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toBeVisible()
  })

  test('topic and face panels stay plain-language', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/')
    await enterSolarSystem(page)

    await page.getByRole('button', { name: /AI Futures/ }).first().click()
    await expect(page.getByRole('heading', { name: 'AI Futures' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Opinions' })).toBeVisible()
    await expect(page.getByLabel('View colors, loudest first')).toContainText('Gold')
    await expect(page.getByRole('button', { name: /Back to the sky|All topics/ })).toBeVisible()

    if (testInfo.project.name === 'mobile') {
      await expect(page.getByRole('banner').getByText('Back', { exact: true })).toBeVisible()
    }

    await page.getByRole('button', { name: /Job Displacement/ }).click()
    await expect(page.getByRole('heading', { name: 'Example posts' })).toBeVisible()
    await expect(page.locator('.caveat')).toContainText('smooths over disagreement')
  })
})
