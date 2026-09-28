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

    await expect.poll(async () => {
      const sun = await page.locator('.observatory canvas').evaluate((canvas) => {
        const width = canvas.width
        const height = canvas.height
        const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
        if (!gl || width < 8 || height < 8) return { r: 0, g: 0, b: 0 }
        const size = 10
        const pixels = new Uint8Array(size * size * 4)
        const x = Math.max(0, Math.floor(width / 2 - size / 2))
        const y = Math.max(0, Math.floor(height / 2 - size / 2))
        gl.readPixels(x, y, size, size, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
        let r = 0
        let g = 0
        let b = 0
        const samples = size * size
        for (let i = 0; i < pixels.length; i += 4) {
          r += pixels[i]
          g += pixels[i + 1]
          b += pixels[i + 2]
        }
        return { r: r / samples, g: g / samples, b: b / samples }
      })
      return sun.r > 150 && sun.g > 120 && sun.r + sun.g > 280
    }, { timeout: 20_000 }).toBeTruthy()

    await page.getByRole('button', { name: 'Show orbit lines' }).click()
    await expect(page.getByRole('button', { name: 'Hide orbit lines' })).toBeVisible()

    if (testInfo.project.name === 'mobile') {
      await expect(page.getByLabel('Choose which topics fill the solar system')).toBeVisible()
      await expect(page.getByText(/Drag the sky to look around/)).toBeVisible()
      const rail = page.getByLabel("Today's planets")
      await expect(rail).toBeVisible()
      await expect(rail.getByRole('button').first()).toContainText('AI Futures')
      await expect(rail.getByRole('button').first()).toContainText('of attention')
      await expect(rail).not.toContainText('Mercury')
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
    await expect(page.getByLabel('View colors, loudest first')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Back to the sky|All topics/ })).toBeVisible()

    if (testInfo.project.name === 'mobile') {
      await expect(page.getByRole('banner').getByText('Back', { exact: true })).toBeVisible()
    }

    await page.getByRole('button', { name: /Job Displacement/ }).click()
    await expect(page.getByRole('heading', { name: 'Example posts' })).toBeVisible()
    await expect(page.locator('.caveat')).toContainText('smooths over disagreement')
  })

  test('hamburger opens site pages with methodology graphics', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/')
    await enterSolarSystem(page)

    await page.getByRole('button', { name: 'Open menu' }).click()
    const menu = page.getByRole('dialog', { name: 'Perspectiverse' })
    await expect(menu.getByRole('button', { name: /Vision/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /About Perspectiverse/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /About the author/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Connect/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Methodology/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /^FAQ/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Donate/ })).toBeVisible()

    await menu.getByRole('button', { name: /Methodology/ }).click()
    await expect(page).toHaveURL(/page=methodology/)
    await expect(page.getByRole('heading', { name: 'How the sky is made' })).toBeVisible()
    await expect(page.getByRole('img', { name: /public talk to a sky/i })).toBeVisible()
    await expect(page.getByRole('img', { name: /Bluesky through the daily job/i })).toBeVisible()
    await expect(page.getByText('Bluesky public search')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Sample a week of talk' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Find neighborhoods in the words' })).toBeVisible()

    await page.getByRole('button', { name: 'Next: FAQ' }).click()
    await expect(page).toHaveURL(/page=faq/)
    await expect(page.getByRole('heading', { name: 'Questions people actually ask' })).toBeVisible()
    await page.getByText('What does planet size mean?').click()
    await expect(page.getByText(/Share of attention in this sample/)).toBeVisible()

    await page.getByRole('button', { name: 'Open menu' }).click()
    await page.getByRole('dialog', { name: 'Perspectiverse' }).getByRole('button', { name: /Donate/ }).click()
    await expect(page.getByRole('link', { name: 'Sponsor on GitHub' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Star the repository' })).toBeVisible()

    await page.getByRole('button', { name: 'Back to the solar system' }).click()
    await expect(page).not.toHaveURL(/page=/)
    await expect(page.locator('.observatory canvas')).toBeVisible()
  })

  test('site pages load from the URL without the welcome tour', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.removeItem('perspectiverse.hide-welcome')
    })
    await page.goto('/?page=author')
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Michael Link' })).toBeVisible()
    await expect(page.getByText(/analytics engineer in Austin/)).toBeVisible()
    await expect(page.getByRole('link', { name: /Data-Science-Link/ })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Michael Link' })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/data-science-link',
    )

    await page.goto('/?page=vision')
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Out of the chamber, into the argument' })).toBeVisible()
    await expect(page.getByText('Public attention', { exact: true })).toBeVisible()
    await expect(page.getByText(/Truth can be nuanced/)).toBeVisible()

    await page.goto('/?page=connect')
    await expect(page.getByRole('heading', { name: 'Say hello' })).toBeVisible()
    await expect(page.getByText(/Michael Link is in Austin/)).toBeVisible()
    await expect(page.getByRole('link', { name: /^GitHub/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /LinkedIn/ })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/data-science-link',
    )
    await expect(page.getByRole('link', { name: /This repository/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /Send feedback/ })).toBeVisible()
  })
})
