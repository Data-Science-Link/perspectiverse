import { expect, test } from '@playwright/test'

async function enterSolarSystem(page) {
  const welcome = page.getByRole('dialog', { name: 'Perspectiverse' })
  if (await welcome.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: 'Enter the solar system' }).click()
    await expect(welcome).toBeHidden()
  }
}

function glyphHeight(page) {
  return page.locator('.sponsor-flyby-banner-text').evaluate((node) => node.getBoundingClientRect().height)
}

async function sampleTowFlight(page, frames = 48) {
  return page.evaluate(async (frameCount) => {
    const sleep = () => new Promise((resolve) => {
      requestAnimationFrame(resolve)
    })

    const gaps = []
    const pillTravel = []
    const clearOpacities = []
    const fadeOpacities = []
    let ruleViolations = 0
    let lastPill = null

    for (let i = 0; i < frameCount; i += 1) {
      await sleep()
      const screen = document.querySelector('.sponsor-flyby-screen')
      const ship = document.querySelector('[data-sponsor-ship]')
      const pill = document.querySelector('.sponsor-flyby-banner')
      if (!screen || screen.style.visibility !== 'visible' || !ship || !pill) continue

      const shipRect = ship.getBoundingClientRect()
      const pillRect = pill.getBoundingClientRect()
      const shipMidX = shipRect.left + shipRect.width / 2
      const edgeGap = pillRect.left >= shipMidX
        ? pillRect.left - shipRect.right
        : shipRect.left - pillRect.right
      gaps.push(Math.max(0, edgeGap))

      if (lastPill) {
        pillTravel.push(Math.hypot(pillRect.left - lastPill.left, pillRect.top - lastPill.top))
      }
      lastPill = { left: pillRect.left, top: pillRect.top }

      const opacity = parseFloat(window.getComputedStyle(pill).opacity)
      let overlapsLabel = false
      document.querySelectorAll('.observatory .planet-label').forEach((label) => {
        const lr = label.getBoundingClientRect()
        const overlapW = Math.min(lr.right, pillRect.right) - Math.max(lr.left, pillRect.left)
        const overlapH = Math.min(lr.bottom, pillRect.bottom) - Math.max(lr.top, pillRect.top)
        if (overlapW > 4 && overlapH > 4) overlapsLabel = true
      })
      if (!overlapsLabel) {
        clearOpacities.push(opacity)
        if (opacity < 0.99) ruleViolations += 1
      } else {
        fadeOpacities.push(opacity)
        if (opacity > 0.25) ruleViolations += 1
      }
    }

    const pillDistance = pillTravel.reduce((sum, value) => sum + value, 0)
    const sortedGaps = [...gaps].sort((a, b) => a - b)
    const p95Gap = sortedGaps.length
      ? sortedGaps[Math.min(sortedGaps.length - 1, Math.floor(sortedGaps.length * 0.95))]
      : 0
    return {
      maxGap: gaps.length ? Math.max(...gaps) : 0,
      p95Gap,
      gapSamples: gaps.length,
      pillDistance,
      minClearOpacity: clearOpacities.length ? Math.min(...clearOpacities) : null,
      clearSamples: clearOpacities.length,
      fadeSamples: fadeOpacities.length,
      maxFadeOpacity: fadeOpacities.length ? Math.max(...fadeOpacities) : null,
      ruleViolations,
    }
  }, frames)
}

test.describe('Sponsor flyby placeholder', () => {
  test('screen-space banner is legible, in view, and click-through', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=1')
    await enterSolarSystem(page)

    const text = page.locator('.sponsor-flyby-banner-text')
    await expect.poll(async () => page.evaluate(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    })).toBe(true)
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
    await expect.poll(async () => page.evaluate(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    })).toBe(true)

    const hit = await page.locator('.sponsor-flyby-banner-text').evaluate((node) => {
      const rect = node.getBoundingClientRect()
      const x = rect.left + rect.width / 2
      const y = rect.top + rect.height / 2
      const target = document.elementFromPoint(x, y)
      return target?.closest?.('.sponsor-flyby-screen') != null
    })
    expect(hit).toBe(false)
  })

  test('pill stays towed to the ship during an animated flight', async ({ page }) => {
    test.setTimeout(120_000)
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=animate')
    await enterSolarSystem(page)
    await expect.poll(async () => page.evaluate(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    })).toBe(true)

    await page.waitForTimeout(400)
    const stats = await sampleTowFlight(page, 56)
    expect(stats.gapSamples).toBeGreaterThanOrEqual(16)
    expect(stats.pillDistance).toBeGreaterThan(40)
    expect(stats.p95Gap).toBeLessThan(56)
    expect(stats.maxGap).toBeLessThan(96)
  })

  test('pill stays fully opaque when it does not overlap labels', async ({ page }, testInfo) => {
    test.setTimeout(120_000)
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=animate')
    await enterSolarSystem(page)
    if (testInfo.project.name === 'mobile') {
      await page.getByRole('button', { name: 'Linear' }).click()
      await expect(page.getByRole('button', { name: 'Orbits' })).toBeVisible()
    }
    await expect.poll(async () => page.evaluate(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    }), { timeout: 20_000 }).toBe(true)

    const stats = await sampleTowFlight(page, 56)
    expect(stats.ruleViolations).toBe(0)
    if (stats.clearSamples > 0) {
      expect(stats.minClearOpacity ?? 0).toBeGreaterThanOrEqual(0.99)
    }
    if (stats.fadeSamples > 0) {
      expect(stats.maxFadeOpacity ?? 1).toBeLessThanOrEqual(0.25)
    }
  })

  async function openLinearWithSponsor(page) {
    await page.addInitScript(() => {
      window.localStorage.setItem('perspectiverse.hide-welcome', '1')
    })
    await page.goto('/?sponsorFlyby=1&sponsorProgress=0.5')
    await enterSolarSystem(page)
    await page.getByRole('button', { name: 'Linear' }).click()
    await expect(page.getByRole('button', { name: 'Orbits' })).toBeVisible()
    await expect.poll(async () => page.evaluate(() => {
      const el = document.querySelector('.sponsor-flyby-screen')
      return el?.style.visibility === 'visible'
    }), { timeout: 20_000 }).toBe(true)
  }

  test('linear view shows sponsor banner without blocking planet labels', async ({ page }, testInfo) => {
    await openLinearWithSponsor(page)

    const text = page.locator('.sponsor-flyby-banner-text')
    await expect(text).toHaveText('Does Advertising Work? Just Did!')
    await expect.poll(async () => glyphHeight(page)).toBeGreaterThanOrEqual(14)

    const layout = await page.evaluate(() => {
      const pill = document.querySelector('.sponsor-flyby-banner')?.getBoundingClientRect()
      const canvas = document.querySelector('.observatory canvas')?.getBoundingClientRect()
      const filter = document.getElementById('solar-topic-filter')?.getBoundingClientRect()
      const labels = [...document.querySelectorAll('.observatory .planet-label')].map((node) => ({
        rect: node.getBoundingClientRect(),
      }))
      return { pill, canvas, filter, labels }
    })
    expect(layout.pill).toBeTruthy()
    expect(layout.canvas).toBeTruthy()
    expect(layout.pill.right).toBeLessThanOrEqual(layout.canvas.right + 2)
    expect(layout.pill.left).toBeGreaterThanOrEqual(layout.canvas.left - 2)
    expect(layout.pill.top).toBeGreaterThanOrEqual(layout.canvas.top - 2)

    if (testInfo.project.name === 'mobile' && layout.filter) {
      expect(layout.pill.bottom).toBeLessThanOrEqual(layout.filter.top - 6)
    }

    const pillArea = layout.pill.width * layout.pill.height
    let labelOverlap = 0
    for (const { rect } of layout.labels) {
      const w = Math.min(rect.right, layout.pill.right) - Math.max(rect.left, layout.pill.left)
      const h = Math.min(rect.bottom, layout.pill.bottom) - Math.max(rect.top, layout.pill.top)
      if (w > 4 && h > 4) labelOverlap += w * h
    }
    expect(labelOverlap).toBeLessThan(pillArea * 0.55)

    const label = page.locator('.observatory .planet-label').first()
    const labelBox = await label.boundingBox()
    expect(labelBox).toBeTruthy()
    const blocked = await page.evaluate(({ x, y }) => {
      const target = document.elementFromPoint(x, y)
      return target?.closest?.('.sponsor-flyby-screen') != null
    }, { x: labelBox.x + labelBox.width / 2, y: labelBox.y + labelBox.height / 2 })
    expect(blocked).toBe(false)
    await page.mouse.click(labelBox.x + labelBox.width / 2, labelBox.y + labelBox.height / 2)
    await expect(page.getByRole('button', { name: 'Read more …' })).toBeVisible()
  })
})
