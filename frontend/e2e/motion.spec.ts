/// <reference lib="dom" />
/// <reference lib="dom.iterable" />
import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { axeViolations } from './axe.js'

const reports = (page: Page) => page.getByRole('list', { name: 'Reports' })
const panel = (page: Page) =>
  page.getByRole('region', { name: 'Report detail' })

async function signIn(page: Page) {
  const demo = JSON.parse(
    await readFile(new URL('./.auth/demo.json', import.meta.url), 'utf8'),
  ) as { email: string; password: string }
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(demo.email)
  await page.getByLabel('Password').fill(demo.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await expect(reports(page).getByRole('link').first()).toBeVisible()
}

test.describe('Motion', () => {
  test.use({
    reducedMotion: 'no-preference',
    viewport: { width: 1280, height: 860 },
  })

  test('report selection keeps the page, panel slot, and filters', async ({
    page,
  }) => {
    await signIn(page)
    const root = page.locator('.animate-page-enter')
    await root.evaluate((element) =>
      element.setAttribute('data-original-page', 'true'),
    )
    await reports(page).getByRole('link').first().click()
    await expect(panel(page).getByRole('heading', { level: 2 })).toBeVisible()
    const slot = page.locator('.animate-panel-enter')
    await expect(slot).toHaveCSS('animation-name', 'enter')
    await expect(slot).toHaveCSS('position', 'sticky')
    await slot.evaluate((element) =>
      element.setAttribute('data-original-slot', 'true'),
    )
    await panel(page).evaluate((element) =>
      element.setAttribute('data-original-panel', 'true'),
    )
    await page.evaluate(() => {
      for (const element of document.querySelectorAll(
        '.animate-page-enter, .animate-panel-enter',
      )) {
        element.setAttribute('data-replays', '0')
        element.addEventListener('animationstart', (event) => {
          if (event.target === element)
            element.setAttribute(
              'data-replays',
              String(Number(element.getAttribute('data-replays')) + 1),
            )
        })
      }
    })
    await reports(page).getByRole('link').nth(1).click()
    await expect(panel(page)).not.toHaveAttribute('data-original-panel', 'true')
    await expect(panel(page).getByRole('heading', { level: 2 })).toBeVisible()
    await expect(slot).toHaveAttribute('data-original-slot', 'true')
    await expect(root).toHaveAttribute('data-original-page', 'true')
    await expect(slot).toHaveAttribute('data-replays', '0')
    await expect(root).toHaveAttribute('data-replays', '0')
    await expect(panel(page).locator('.animate-content-enter')).toHaveCSS(
      'animation-name',
      'enter',
    )
    await expect(
      page.getByRole('searchbox', { name: 'Search reports' }),
    ).toHaveValue('')
    await page.getByRole('link', { name: 'Problems', exact: true }).click()
    await expect(
      page.getByRole('heading', { name: 'Problems', exact: true }),
    ).toBeVisible()
    await expect(page.locator('.animate-page-enter')).not.toHaveAttribute(
      'data-original-page',
      'true',
    )
    await expect(page.locator('.animate-page-enter')).toHaveCSS(
      'animation-duration',
      '0.22s',
    )
  })

  test('background refresh animates only the new row with capped stagger', async ({
    page,
  }) => {
    await page.clock.install()
    await signIn(page)
    const rows = reports(page).getByRole('listitem')
    const starts = await rows.evaluateAll((elements) =>
      elements.map((element) => {
        element.setAttribute('data-original-row', 'true')
        return element.getAnimations()[0].startTime
      }),
    )
    await page.route(/\/api\/workspaces\/[^/]+\/reports\/$/, async (route) => {
      const response = await route.fetch()
      const data = await response.json()
      data.results.push({
        ...data.results[0],
        id: 'motion-new-row',
        title: 'Motion refresh row',
      })
      data.count += 1
      await route.fulfill({ response, json: data })
    })
    // Advance the real list refresh timer without waiting thirty seconds.
    await page.clock.fastForward(30_000)
    await expect(
      reports(page).getByRole('link', { name: 'Motion refresh row' }),
    ).toBeVisible()
    expect(
      await reports(page)
        .locator('[data-original-row]')
        .evaluateAll((elements) =>
          elements.map((element) => element.getAnimations()[0].startTime),
        ),
    ).toEqual(starts)
    const newRow = rows.last()
    await expect(newRow).toHaveCSS('animation-name', 'enter')
    await expect(newRow).toHaveCSS('animation-duration', '0.16s')
    await expect(newRow).toHaveCSS(
      'animation-delay',
      `${(Math.min(starts.length, 10) * 22) / 1000}s`,
    )
  })

  test('follow-up switches reuse the panel slot', async ({ page }) => {
    await signIn(page)
    await page.getByRole('link', { name: 'Follow-ups', exact: true }).click()
    const list = page.getByRole('list', { name: 'Follow-ups' })
    await list.getByRole('link').first().click()
    const slot = page.locator('.animate-panel-enter')
    await expect(slot).toHaveCSS('animation-name', 'enter')
    await slot.evaluate((element) =>
      element.setAttribute('data-original-slot', 'true'),
    )
    await list.getByRole('link').nth(1).click()
    await expect(slot).toHaveAttribute('data-original-slot', 'true')
    await expect(
      page
        .getByRole('region', { name: 'Follow-up detail' })
        .locator('.animate-content-enter'),
    ).toBeVisible()
  })

  test('the report panel sticks beside a long list', async ({ page }) => {
    await page.route(/\/api\/workspaces\/[^/]+\/reports\/$/, async (route) => {
      const response = await route.fetch()
      const data = await response.json()
      data.results.push(
        ...Array.from({ length: 20 }, (_, index) => ({
          ...data.results[0],
          id: `motion-scroll-${index}`,
          title: `Scroll report ${index}`,
        })),
      )
      data.count = data.results.length
      await route.fulfill({ response, json: data })
    })
    await signIn(page)
    await reports(page).getByRole('link').first().click()
    await expect(panel(page).getByRole('heading', { level: 2 })).toBeVisible()
    const slot = page.locator('.animate-panel-enter')
    await slot.evaluate((element) =>
      Promise.all(
        element.getAnimations().map((animation) => animation.finished),
      ),
    )
    const inset = await slot.evaluate((element) =>
      parseFloat(getComputedStyle(element).top),
    )
    await page.evaluate(() => window.scrollTo(0, 400))
    await expect.poll(async () => (await slot.boundingBox())?.y).toBe(inset)
    await page.evaluate(() => window.scrollTo(0, 500))
    await expect.poll(async () => (await slot.boundingBox())?.y).toBe(inset)
    await reports(page)
      .getByRole('link')
      .nth(1)
      .evaluate((element) => (element as HTMLElement).click())
    await expect(panel(page).getByRole('heading', { level: 2 })).toHaveText(
      await reports(page)
        .getByRole('link')
        .nth(1)
        .locator('.font-medium')
        .nth(1)
        .innerText(),
    )
    expect(await page.evaluate(() => window.scrollY)).toBe(500)
  })

  for (const scheme of ['light', 'dark'] as const) {
    test(`gallery press feedback and hairline shadows in ${scheme}`, async ({
      page,
    }) => {
      await page.emulateMedia({ colorScheme: scheme })
      await signIn(page)
      await page.goto('/dev/ui')
      await expect(
        page.getByRole('heading', { name: 'Motion', exact: true }),
      ).toBeVisible()
      const button = page.getByRole('button', {
        name: 'Primary action',
        exact: true,
      })
      await button.hover()
      await page.mouse.down()
      try {
        await expect(button).toHaveCSS('scale', '0.97')
      } finally {
        await page.mouse.up()
      }
      await expect(
        page.getByRole('button', { name: 'Outline action' }),
      ).not.toHaveCSS('box-shadow', 'none')
      await expect(
        page.getByRole('button', { name: 'Muted action' }),
      ).not.toHaveCSS('box-shadow', 'none')
      await expect(
        page.locator('[data-slot="status-badge"]').first(),
      ).toHaveCSS('transition-duration', '0.16s, 0.16s')
      const sample = page.locator('.animate-page-enter')
      await sample.evaluate((element) =>
        element.setAttribute('data-before-replay', 'true'),
      )
      await page.getByRole('button', { name: 'Replay motion' }).click()
      await expect(sample).not.toHaveAttribute('data-before-replay', 'true')
    })
  }

  test('dark raised surfaces keep contrast', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' })
    await signIn(page)
    await reports(page).getByRole('link').first().click()
    await expect(panel(page).getByRole('heading', { level: 2 })).toBeVisible()
    const surfaces = await page.evaluate(() => {
      const probe = document.createElement('div')
      document.body.append(probe)
      probe.style.backgroundColor = 'var(--raised)'
      const raised = getComputedStyle(probe).backgroundColor
      probe.style.backgroundColor = 'var(--card)'
      const card = getComputedStyle(probe).backgroundColor
      probe.remove()
      return { raised, card }
    })
    expect(surfaces.raised).not.toBe(surfaces.card)
    await expect(panel(page)).toHaveCSS('background-color', surfaces.raised)
    await expect(reports(page).locator('..')).toHaveCSS(
      'background-color',
      surfaces.card,
    )
    expect(await axeViolations(page, ['color-contrast'])).toEqual([])
  })
})

test.describe('Reduced motion', () => {
  test.use({ reducedMotion: 'reduce' })

  test('page, content, rows, panels, badges, and buttons stay still', async ({
    page,
  }) => {
    await signIn(page)
    await expect(page.locator('.animate-page-enter')).toHaveCSS(
      'animation-name',
      'none',
    )
    await expect(reports(page).getByRole('listitem').first()).toHaveCSS(
      'animation-name',
      'none',
    )
    await reports(page).getByRole('link').first().click()
    await expect(panel(page).getByRole('heading', { level: 2 })).toBeVisible()
    await expect(page.locator('.animate-panel-enter')).toHaveCSS(
      'animation-name',
      'none',
    )
    await expect(panel(page).locator('.animate-content-enter')).toHaveCSS(
      'animation-name',
      'none',
    )
    await expect(
      panel(page).locator('[data-slot="status-badge"]').first(),
    ).toHaveCSS('transition-duration', '0s')
    const button = page.getByRole('link', { name: 'New report' })
    await button.hover()
    await page.mouse.down()
    try {
      await expect(button).toHaveCSS('scale', 'none')
      await expect(button).toHaveCSS('transition-duration', '0s')
    } finally {
      await page.mouse.up()
    }
  })
})
