import { expect, test } from '@playwright/test'
import { axeViolations } from './axe.js'
import { saveSeedSession, seedSessionPath } from './seed-session.js'

type PageOfIds = { results: { id: string }[] }

const sessionPath = seedSessionPath('product-states')
const routes = new Map<string, string>()

test.beforeAll(async ({ browser }, info) => {
  const seed = await saveSeedSession(
    browser,
    info.project.use.baseURL,
    sessionPath,
  )
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL,
    storageState: sessionPath,
  })
  try {
    const endpoints = [
      ['report', 'reports'],
      ['problem', 'problems'],
      ['follow-up', 'follow-ups'],
    ] as const
    for (const [kind, endpoint] of endpoints) {
      const response = await context.request.get(
        `/api/workspaces/${seed.workspace_id}/${endpoint}/`,
      )
      expect(response.ok(), `Could not load seeded ${kind} records`).toBe(true)
      const data = (await response.json()) as PageOfIds
      const id = data.results[0]?.id
      if (id)
        routes.set(
          kind,
          `/${endpoint === 'reports' ? 'inbox' : endpoint}/${id}`,
        )
    }
  } finally {
    await context.close()
  }
})

test.use({ storageState: sessionPath })

const productRoutes = [
  { name: '/inbox', path: '/inbox' },
  { name: '/inbox/new', path: '/inbox/new' },
  { name: '/problems', path: '/problems' },
  { name: '/follow-ups', path: '/follow-ups' },
  { name: '/settings', path: '/settings' },
  { name: '/inbox/:reportId', key: 'report' },
  { name: '/problems/:problemId', key: 'problem' },
  { name: '/follow-ups/:followUpId', key: 'follow-up' },
  { name: '/invite/unknown-token', path: '/invite/unknown-token' },
] as const

for (const productRoute of productRoutes) {
  test(`${productRoute.name} fits narrow screens, accepts keyboard entry, and passes axe`, async ({
    page,
  }) => {
    const route =
      'path' in productRoute ? productRoute.path : routes.get(productRoute.key)
    expect(
      route,
      `No seeded ${'key' in productRoute ? productRoute.key : 'route'} record was found. Run the full E2E suite to seed records.`,
    ).toBeTruthy()

    for (const width of [375, 320]) {
      await page.setViewportSize({ width, height: 740 })
      await page.goto(route!)
      await page.waitForLoadState('networkidle')
      await expect(page.locator('main')).toBeVisible()
      await page.keyboard.press('Tab')
      expect(
        await page.evaluate('document.activeElement !== document.body'),
        `${productRoute.name} at ${width}px should accept keyboard focus`,
      ).toBe(true)
      expect(
        await page.evaluate(
          'document.documentElement.scrollWidth <= innerWidth',
        ),
        `${productRoute.name} at ${width}px should not overflow horizontally`,
      ).toBe(true)
      if (width === 320)
        expect(await axeViolations(page), productRoute.name).toEqual([])
    }
  })
}
