import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

async function waitForScene(page: Page): Promise<void> {
  // Graphics startup has a separate budget from motion behavior checks.
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-renderer',
    'webgl',
    { timeout: 15000 },
  )
}

test('public content, keyboard navigation, and optional app link', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Customer feedback, carried through to a fix',
  )
  await expect(page.getByRole('heading', { level: 3 })).toHaveText([
    'Capture',
    'Connect',
    'Follow up',
  ])
  await page.keyboard.press('Tab')
  await expect(
    page.getByRole('link', { name: 'Skip to content' }),
  ).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/#main$/)
  const link = page.getByRole('link', { name: 'Sign in' })
  if (process.env.MARKETING_APP_URL)
    await expect(link).toHaveAttribute('href', process.env.MARKETING_APP_URL)
  else await expect(link).toHaveCount(0)
  await expect(
    page.getByRole('link', { name: 'Explore the project' }),
  ).toHaveAttribute('href', 'https://github.com/nicoleman0/rescribo')
})
for (const width of [320, 390, 720, 768, 1440]) {
  test(`accessible layout at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await page.evaluate(() => document.fonts.ready)
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
          .analyze()
      ).violations,
    ).toEqual([])
  })
}
test('content and navigation without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false })
  const page = await context.newPage()
  await page.goto('http://127.0.0.1:4176/')
  await expect(
    page.getByRole('heading', { name: 'Capture', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.fallback')).toBeVisible()
  await expect(page.locator('#motion-control')).toBeHidden()
  await page.getByRole('link', { name: 'The workflow', exact: true }).click()
  await expect(page).toHaveURL(/#workflow$/)
  if (process.env.MARKETING_APP_URL)
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      process.env.MARKETING_APP_URL,
    )
  await context.close()
})
test('static fallback when WebGL cannot initialize', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      ...args: Parameters<typeof original>
    ) {
      if (String(args[0]).startsWith('webgl')) return null
      return original.apply(this, args)
    } as typeof original
  })
  await page.goto('/')
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-renderer',
    'static',
  )
  await expect(page.locator('.fallback')).toBeVisible()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
})
test('actual context loss restores the fallback', async ({ page }) => {
  await page.goto('/')
  await waitForScene(page)
  await page.locator('#scene').evaluate((element) => {
    const extension = (element as HTMLCanvasElement)
      .getContext('webgl2')
      ?.getExtension('WEBGL_lose_context')
    if (!extension)
      throw new Error('Test browser does not support context-loss simulation')
    extension.loseContext()
  })
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-renderer',
    'static',
  )
  await expect(page.locator('.fallback')).toBeVisible()
  await expect(page.locator('#motion-control')).toBeHidden()
})
test('keyboard pause freezes the rendered composition and resumes', async ({
  page,
}) => {
  await page.goto('/')
  await waitForScene(page)
  const visual = page.locator('#visual')
  const control = page.locator('#motion-control')
  await expect(visual).toHaveAttribute('data-motion', 'running')
  await control.focus()
  await page.keyboard.press('Space')
  await expect(control).toHaveText('Resume motion')
  await expect(control).toHaveAttribute('aria-pressed', 'true')
  const before = await page.locator('#scene').screenshot()
  await page.mouse.move(800, 450)
  await page.waitForTimeout(200)
  expect(await page.locator('#scene').screenshot()).toEqual(before)
  await page.keyboard.press('Space')
  await expect(visual).toHaveAttribute('data-motion', 'running')
})
test('pointer movement changes the rendered composition', async ({ page }) => {
  await page.addInitScript(() => {
    const request = window.requestAnimationFrame.bind(window)
    window.requestAnimationFrame = (callback) => request(() => callback(0))
  })
  await page.goto('/')
  await waitForScene(page)
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-motion',
    'running',
  )
  const canvas = page.locator('#scene')
  const before = await canvas.screenshot()
  await canvas.hover({ position: { x: 40, y: 50 } })
  await page.waitForTimeout(250)
  expect(await canvas.screenshot()).not.toEqual(before)
})
test('initial and changing reduced-motion preference stops all motion', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await waitForScene(page)
  const visual = page.locator('#visual')
  await expect(visual).toHaveAttribute('data-renderer', 'webgl')
  await expect(visual).toHaveAttribute('data-motion', 'stopped')
  await expect(
    page.getByRole('button', { name: 'Reduced motion' }),
  ).toBeDisabled()
  const before = await page.locator('#scene').screenshot()
  await page.mouse.move(850, 300)
  await page.waitForTimeout(200)
  expect(await page.locator('#scene').screenshot()).toEqual(before)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(visual).toHaveAttribute('data-motion', 'running')
  await expect(page.locator('#motion-control')).toHaveText('Pause motion')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(visual).toHaveAttribute('data-motion', 'stopped')
})
test('offscreen visual suspends and returns without losing manual pause', async ({
  page,
}) => {
  await page.goto('/')
  await waitForScene(page)
  const visual = page.locator('#visual')
  await expect(visual).toHaveAttribute('data-motion', 'running')
  await page.locator('footer').scrollIntoViewIfNeeded()
  await expect(visual).toHaveAttribute('data-motion', 'stopped')
  await visual.scrollIntoViewIfNeeded()
  await expect(visual).toHaveAttribute('data-motion', 'running')
  await page.getByRole('button', { name: 'Pause motion' }).click()
  await page.locator('footer').scrollIntoViewIfNeeded()
  await visual.scrollIntoViewIfNeeded()
  await expect(visual).toHaveAttribute('data-motion', 'stopped')
})
test('page lifecycle tears down and restores graphics for back-forward cache', async ({
  page,
}) => {
  await page.goto('/')
  await waitForScene(page)
  const visual = page.locator('#visual')
  await expect(visual).toHaveAttribute('data-renderer', 'webgl')
  await page.evaluate(() =>
    window.dispatchEvent(
      new PageTransitionEvent('pagehide', { persisted: true }),
    ),
  )
  await expect(visual).toHaveAttribute('data-renderer', 'static')
  await page.evaluate(() =>
    window.dispatchEvent(
      new PageTransitionEvent('pageshow', { persisted: true }),
    ),
  )
  await expect(visual).toHaveAttribute('data-renderer', 'webgl')
  await expect(visual).toHaveAttribute('data-motion', 'running')
})

test('hidden document suspends animation', async ({ page }) => {
  await page.goto('/')
  await waitForScene(page)
  const visual = page.locator('#visual')
  await expect(visual).toHaveAttribute('data-motion', 'running')
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => true,
    })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect(visual).toHaveAttribute('data-motion', 'stopped')
  await page.evaluate(() => {
    delete (document as unknown as { hidden?: boolean }).hidden
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect(visual).toHaveAttribute('data-motion', 'running')
})

test('native scroll changes the rendered 3D pose and reverses', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.addInitScript(() => {
    const request = window.requestAnimationFrame.bind(window)
    window.requestAnimationFrame = (callback) => request(() => callback(0))
  })
  await page.goto('/')
  await waitForScene(page)
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-motion',
    'running',
  )
  const canvas = page.locator('#scene')
  const initial = await canvas.screenshot()
  await page.evaluate(() => window.scrollTo({ top: 200, behavior: 'instant' }))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(200)
  await page.waitForTimeout(700)
  const scrolled = await canvas.screenshot()
  expect(scrolled).not.toEqual(initial)
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  await page.waitForTimeout(700)
  expect(await canvas.screenshot()).not.toEqual(scrolled)
})

for (const mode of ['pause', 'reduce'] as const) {
  test(`scroll leaves the rendered scene unchanged under ${mode}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    if (mode === 'reduce') await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')
    await waitForScene(page)
    if (mode === 'pause')
      await page.getByRole('button', { name: 'Pause motion' }).click()
    await expect(page.locator('#visual')).toHaveAttribute(
      'data-motion',
      'stopped',
    )
    const before = await page.locator('#scene').screenshot()
    await page.evaluate(() =>
      window.scrollTo({ top: 200, behavior: 'instant' }),
    )
    await page.waitForTimeout(250)
    expect(await page.locator('#scene').screenshot()).toEqual(before)
    const row = page.locator('.steps li').first()
    const transform = await row.evaluate(
      (element) => getComputedStyle(element).transform,
    )
    await page.locator('footer').scrollIntoViewIfNeeded()
    await expect(page.locator('#motion-control')).toBeInViewport()
    await expect(
      page.getByRole('heading', { name: 'Follow up', exact: true }),
    ).toBeVisible()
    expect(
      await row.evaluate((element) => getComputedStyle(element).transform),
    ).toBe(transform)
  })
}

test('workflow scroll animation and its cleanup preserve readable content', async ({
  page,
}) => {
  await page.goto('/')
  await waitForScene(page)
  const row = page.locator('.steps li').first()
  const initial = await row.evaluate(
    (element) => getComputedStyle(element).transform,
  )
  await row.scrollIntoViewIfNeeded()
  await expect
    .poll(() => row.evaluate((element) => getComputedStyle(element).transform))
    .not.toBe(initial)
  await expect(row.getByRole('heading', { name: 'Capture' })).toBeVisible()
  await page.evaluate(() =>
    window.dispatchEvent(
      new PageTransitionEvent('pagehide', { persisted: true }),
    ),
  )
  await expect(row).toHaveCSS('transform', 'none')
})

test('persistent motion control does not cover footer navigation', async ({
  page,
}) => {
  await page.goto('/')
  await waitForScene(page)
  await page.route(
    'https://github.com/nicoleman0/rescribo/blob/main/LICENSE',
    (route) =>
      route.fulfill({
        contentType: 'text/html',
        body: '<title>License</title>',
      }),
  )
  await page.locator('footer').scrollIntoViewIfNeeded()
  await expect(page.locator('#motion-control')).toBeInViewport()
  await page.getByRole('link', { name: 'AGPL-3.0 license' }).click()
  await expect(page).toHaveURL(
    'https://github.com/nicoleman0/rescribo/blob/main/LICENSE',
  )
})

test('delayed graphics startup still supports keyboard pause', async ({
  page,
}) => {
  await page.route('**/assets/scene-*.js', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 6000))
    await route.continue()
  })
  await page.goto('/')
  await waitForScene(page)
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-motion',
    'running',
  )
  const control = page.locator('#motion-control')
  await control.focus()
  await page.keyboard.press('Space')
  await expect(control).toHaveText('Resume motion')
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-motion',
    'stopped',
  )
  await page.keyboard.press('Space')
  await expect(page.locator('#visual')).toHaveAttribute(
    'data-motion',
    'running',
  )
})
