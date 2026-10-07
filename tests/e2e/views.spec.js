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
  test('loads a living solar system with onboarding, tagline, and orbit toggle', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.removeItem('perspectiverse.hide-welcome')
    })
    await page.goto('/')

    const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
    await expect(welcome).toBeVisible()
    await expect(welcome.locator('.welcome-steps li')).toHaveCount(4)
    await expect(welcome).toContainText('Each planet is a topic')
    await expect(welcome).toContainText('See Methodology in the menu')
    await expect(welcome).not.toContainText('Jev')
    await expect(welcome).toContainText('See every perspective')
    const fitted = await welcome.evaluate((node) => node.scrollHeight <= node.clientHeight + 1)
    expect(fitted).toBe(true)
    await expect(page.getByLabel("Don't show this again")).toBeVisible()
    await page.getByLabel("Don't show this again").check()
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()

    await expect(page.getByRole('banner').getByText('See every perspective — and where yours stands.')).toBeVisible()
    await expect(page.getByText('Test your take')).toHaveCount(0)
    await expect(page.getByText('Anti-echo')).toHaveCount(0)
    await expect(page.locator('.pv-graphic')).toHaveCount(0)
    if (testInfo.project.name !== 'mobile') {
      await expect(page.getByRole('region', { name: 'This week' })).toBeVisible()
      await expect(page.getByText('Filter topics', { exact: true }).first()).toBeVisible()
    }
    await expect(page.locator('.observatory').getByText('Filter topics', { exact: true })).toBeVisible()
    await expect(page.locator('.observatory').getByLabel('Choose which topics fill the solar system')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Linear' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Show orbit lines' })).toBeVisible()
    const observatoryCanvas = page.locator('.observatory canvas')
    await expect(observatoryCanvas).toBeVisible()
    if (testInfo.project.name === 'mobile') {
      await expect(page.locator('.observatory .planet-label').first()).toBeVisible()
    }

    if (testInfo.project.name !== 'mobile') {
    await expect.poll(async () => {
      const frame = await observatoryStats(page)
      return frame.width > 64 && frame.height > 64 && frame.lit > 8
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
    }

    await page.getByRole('button', { name: 'Show orbit lines' }).click()
    await expect(page.getByRole('button', { name: 'Hide orbit lines' })).toBeVisible()
    await page.getByRole('button', { name: 'Linear' }).click()
    await expect(page.getByRole('button', { name: 'Orbits' })).toBeVisible()
    await expect(page.getByText('Largest to smallest')).toBeVisible()
    await page.getByRole('button', { name: 'Orbits' }).click()
    await expect(page.getByRole('button', { name: 'Linear' })).toBeVisible()

    if (testInfo.project.name === 'mobile') {
      await page.locator('.observatory .planet-label').first().click({ force: true })
    }
    await expect(page.getByRole('button', { name: 'Read more …' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Example posts' })).toBeVisible()
    if (testInfo.project.name !== 'mobile') {
      await expect(page.getByLabel('Choose which topics fill the solar system')).toBeVisible()
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
    await page.getByRole('button', { name: /welcome tour/i }).click()
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toBeVisible()
  })

  test('topic and face panels stay plain-language', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/')
    await enterSolarSystem(page)

    if (testInfo.project.name === 'mobile') {
      await page.locator('.observatory .planet-label').first().click({ force: true })
    } else {
      await page.getByRole('button', { name: 'Perspectives' }).click()
    }
    const perspectiveBars = page.locator('.reading-screen .bar-name')
    await expect.poll(async () => perspectiveBars.count()).toBeGreaterThan(0)
    const perspectiveCount = await perspectiveBars.count()
    expect(perspectiveCount).toBeLessThanOrEqual(6)
    const shares = await perspectiveBars.locator('strong').allInnerTexts()
    if (perspectiveCount > 1) {
      expect(shares.some((share) => share !== '100.0%')).toBe(true)
    }
    const labels = await page.locator('.reading-screen .bar-label').allInnerTexts()
    for (const label of labels) {
      const words = label.toLowerCase().split(/\s+/).filter(Boolean)
      for (let index = 1; index < words.length; index += 1) {
        expect(words[index]).not.toBe(words[index - 1])
      }
    }
    await expect(page.locator('.reading-screen')).not.toContainText(/that is the position in the posts/i)
    await expect(page.locator('.reading-screen')).not.toContainText(/is the claim these posts repeat/i)
    await expect(page.locator('.reading-screen')).not.toContainText(/hope many people will fill/i)
    const briefText = await page.locator('.reading-brief').innerText()
    const briefSentences = briefText.split(/[.!?]+/).map((part) => part.trim()).filter(Boolean)
    expect(briefSentences.length).toBeGreaterThanOrEqual(1)
    expect(briefSentences.length).toBeLessThanOrEqual(5)
    await expect(page.getByRole('button', { name: '← All topics' }).or(page.getByRole('button', { name: '← Back to the solar system' }))).toBeVisible()
    if (testInfo.project.name === 'mobile') {
      await expect(page.getByRole('banner').getByText('Back', { exact: true })).toBeVisible()
    }
    await page.locator('.bar-name').nth(0).click()
    await expect(page.getByRole('heading', { name: 'Example posts' })).toBeVisible()
    await page.getByRole('button', { name: 'Read more …' }).click()
    await expect(page.locator('.reading-detail p')).toHaveCount(3)
    await expect(page.locator('.reading-brief')).toBeVisible()
    if (testInfo.project.name === 'mobile') {
      await expect(page.getByRole('button', { name: 'Back to the planet' })).toBeVisible()
      await expect(page.locator('.reading-band')).toHaveCount(0)
      await page.getByRole('button', { name: 'Back to the planet' }).click()
      await expect(page.locator('.reading-band')).toHaveCount(3)
      const previewCount = await page.locator('.reading-band .post-card').count()
      await page.getByRole('button', { name: 'See all posts' }).click()
      await expect(page.getByRole('button', { name: 'Back to the planet' })).toBeVisible()
      await expect.poll(async () => page.locator('.reading-sheet .post-card').count()).toBeGreaterThanOrEqual(previewCount)
      await page.getByRole('button', { name: 'Back to the planet' }).click()
      await expect(page.locator('.reading-band')).toHaveCount(3)
    }
    await page.getByRole('banner').getByRole('button', { name: 'Email' }).click()
    await expect(page.getByRole('article', { name: 'Weekly email' })).toBeVisible()
    await expect(page.getByRole('heading', { name: /This week/ })).toBeVisible()
    await expect(page.locator('.caveat')).toHaveCount(0)
    await expect(page.getByText(/shorter name/)).toHaveCount(0)
    await expect(page.getByText(/third reply/)).toHaveCount(0)
  })

  test('hamburger opens site pages with methodology graphics', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/')
    await enterSolarSystem(page)

    await page.getByRole('button', { name: 'Open menu' }).click()
    const menu = page.getByRole('dialog', { name: 'Perspectiverse' })
    await expect(menu.getByRole('button', { name: /About/i })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Methodology/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /^FAQ/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Connect/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Donate/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Weekly email digest/i })).toBeVisible()

    await menu.getByRole('button', { name: /Methodology/ }).click()
    await expect(page).toHaveURL(/page=methodology/)
    await expect(page.getByRole('heading', { name: 'How the map is built' })).toBeVisible()
    await expect(page.getByRole('img', { name: /Jev filters to planets/i })).toBeVisible()
    await expect(page.getByText(/Representation, not verdict/i)).toBeVisible()
    await expect(page.locator('.site-page')).toContainText(/steelman/i)
    await expect(page.getByRole('heading', { name: 'Sample a week of talk' })).toBeVisible()
    await expect(page.locator('.site-page')).not.toContainText(/spike/i)
    await expect(page.locator('.site-page')).not.toContainText(/\bcube\b/i)

    await page.getByRole('banner').getByRole('button', { name: 'Universe' }).click()
    await expect(page).not.toHaveURL(/page=/)
    await expect(page.locator('.observatory canvas')).toBeVisible()
    await page.getByRole('button', { name: 'Open menu' }).click()
    await page.getByRole('dialog', { name: 'Perspectiverse' }).getByRole('button', { name: /Methodology/ }).click()

    await page.getByRole('button', { name: 'Next: FAQ' }).click()
    await expect(page).toHaveURL(/page=faq/)
    await expect(page.getByRole('heading', { name: 'Common questions' })).toBeVisible()
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

  test('each planet shows its own post count and Universe returns to the solar system', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/')
    await enterSolarSystem(page)

    const universe = page.getByRole('banner').getByRole('button', { name: 'Universe' })
    await expect(universe).toBeVisible()
    const labels = page.locator('.observatory .planet-label')
    await expect(labels.nth(1)).toBeVisible()
    const secondName = (await labels.nth(1).innerText()).trim()

    await labels.nth(0).click({ force: true })
    const eyebrow = page.locator('.reading-screen .eyebrow')
    await expect(eyebrow).toBeVisible()
    const firstCount = (await eyebrow.innerText()).trim()
    expect(firstCount).toMatch(/\d[\d,]* posts/i)
    expect(firstCount).not.toMatch(/2,805 posts/i)

    await universe.click()
    await expect(page).not.toHaveURL(/topic=/)
    await expect(page.locator('.observatory canvas')).toBeVisible()

    await page.locator('.observatory .planet-label', { hasText: secondName }).first().click({ force: true })
    const secondCount = (await page.locator('.reading-screen .eyebrow').innerText()).trim()
    expect(secondCount).toMatch(/\d[\d,]* posts/i)
    expect(secondCount).not.toEqual(firstCount)

    await universe.click()
    await expect(page.locator('.observatory canvas')).toBeVisible()
    await expect(page.locator('.reading-screen .back-link')).toHaveCount(0)
  })

  test('site pages load from the URL without the welcome tour', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.removeItem('perspectiverse.hide-welcome')
    })
    await page.goto('/?page=author')
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'People and links' })).toBeVisible()
    await expect(page.getByText(/Michael Link \(Austin/)).toBeVisible()
    await expect(page.getByRole('link', { name: /Data-Science-Link/ })).toBeVisible()
    await expect(page.getByRole('link', { name: 'LinkedIn' })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/data-science-link',
    )

    await page.goto('/?page=vision')
    await expect(page.getByRole('dialog', { name: 'Perspectiverse' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: /mapped without taking sides/i })).toBeVisible()
    await expect(page.locator('.site-page')).toContainText(/steelman/i)

    await page.goto('/?page=connect')
    await expect(page.getByRole('heading', { name: 'People and links' })).toBeVisible()
    await expect(page.getByText(/Austin/)).toBeVisible()
    await expect(page.getByRole('link', { name: /^GitHub/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /LinkedIn/ })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/data-science-link',
    )
    await expect(page.getByRole('link', { name: /Repository/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /Feedback/ })).toBeVisible()
  })
})
