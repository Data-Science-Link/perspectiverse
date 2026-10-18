import { expect, test } from '@playwright/test'

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

async function waitForCamera(page) {
  await expect.poll(async () => {
    return page.evaluate(() => Boolean(window.__PV_SOLAR_CAMERA__?.read?.()))
  }, { timeout: 20_000 }).toBeTruthy()
}

async function readCamera(page) {
  return page.evaluate(() => {
    const view = window.__PV_SOLAR_CAMERA__?.read?.()
    if (!view) return null
    return {
      distance: view.distance,
      position: view.position,
      target: view.target,
    }
  })
}

function near(a, b, tolerance = 0.35) {
  return Math.abs(a - b) <= tolerance
}

function viewsMatch(before, after, tolerance = 0.35) {
  if (!before || !after) return false
  if (!near(before.distance, after.distance, tolerance)) return false
  for (let i = 0; i < 3; i += 1) {
    if (!near(before.position[i], after.position[i], tolerance)) return false
    if (!near(before.target[i], after.target[i], tolerance)) return false
  }
  return true
}

async function dollySolarView(page, amount = 0.55) {
  await page.evaluate((delta) => {
    window.__PV_SOLAR_CAMERA__?.dolly?.(delta)
  }, amount)
  await page.waitForTimeout(450)
}

async function homeDistance(page) {
  return page.evaluate(() => window.__PV_SOLAR_CAMERA__?.homeDistance?.() ?? null)
}

async function drillPlanetAndBack(page, testInfo) {
  if (testInfo.project.name === 'mobile') {
    await page.locator('.observatory .planet-label').first().click({ force: true })
  } else {
    await page.getByRole('button', { name: 'Perspectives' }).click()
  }
  await expect(page).toHaveURL(/topic=/)
  if (testInfo.project.name === 'mobile') {
    await page.locator('button.chrome-back').click()
  } else {
    await page.getByRole('button', { name: '← All topics' }).click()
  }
  await expect(page).not.toHaveURL(/topic=/)
  await waitForCamera(page)
  await page.waitForTimeout(700)
}

test.describe('Solar camera restore', () => {
  test('returns to the same zoom and pan after leaving a planet', async ({ page }, testInfo) => {
    await enterSolarSystem(page)
    await waitForCamera(page)
    await dollySolarView(page, 0.65)
    const before = await readCamera(page)
    expect(before?.distance).toBeTruthy()

    await drillPlanetAndBack(page, testInfo)

    const after = await readCamera(page)
    expect(viewsMatch(before, after)).toBe(true)
  })

  test('browser back from a planet restores the solar camera', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', 'Mobile hides the observatory while drilled')
    await enterSolarSystem(page)
    await waitForCamera(page)
    await dollySolarView(page, 0.5)
    const before = await readCamera(page)

    await page.getByRole('button', { name: 'Perspectives' }).click()
    await expect(page).toHaveURL(/topic=/)

    await page.goBack()
    await expect(page).not.toHaveURL(/topic=/)
    await waitForCamera(page)
    await page.waitForTimeout(700)

    const after = await readCamera(page)
    expect(viewsMatch(before, after)).toBe(true)
  })

  test('switching to World after a planet visit uses World home framing', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', 'Category filter lives on the desktop chrome')
    await enterSolarSystem(page)
    await waitForCamera(page)
    await dollySolarView(page, 0.7)
    await drillPlanetAndBack(page, testInfo)
    const zoomed = await readCamera(page)

    await page.locator('#solar-topic-filter').selectOption('World')
    await page.waitForTimeout(900)
    await waitForCamera(page)
    const worldCam = await readCamera(page)
    const worldHome = await homeDistance(page)
    expect(worldHome).toBeTruthy()
    expect(near(worldCam.distance, worldHome, 0.65)).toBe(true)
    expect(worldCam.distance).toBeLessThan(zoomed.distance - 2)
  })

  test('Linear after a planet visit centers the row at home distance', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', 'Linear toggle is on the desktop observatory chrome')
    await enterSolarSystem(page)
    await waitForCamera(page)
    await page.evaluate(() => window.__PV_SOLAR_CAMERA__?.truck?.(5, 0))
    await page.waitForTimeout(400)
    await dollySolarView(page, 0.55)
    await drillPlanetAndBack(page, testInfo)

    await page.getByRole('button', { name: 'Linear' }).click()
    await page.waitForTimeout(900)
    await waitForCamera(page)
    const linearCam = await readCamera(page)
    const linearHome = await homeDistance(page)
    expect(linearHome).toBeTruthy()
    expect(near(linearCam.distance, linearHome, 0.65)).toBe(true)
    expect(Math.abs(linearCam.target[0])).toBeLessThan(1.5)
  })
})
