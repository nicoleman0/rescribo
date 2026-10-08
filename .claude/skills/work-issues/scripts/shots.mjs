// Captures the seeded demo workspace in light and dark at 1280px and 390px.
// From the worktree root, with the dev servers on <web>:
//   RESCRIBO_DEMO_PASSWORD='Rescribo-demo-e2e-2026!' uv run python backend/manage.py seed_demo
//   SHOTS_BASE=http://127.0.0.1:<web> node .claude/skills/work-issues/scripts/shots.mjs <out-dir>
// If a change renames a landmark this script waits for, edit it in that change.
import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import path from 'node:path'

const frontend = path.resolve('frontend')
const base = process.env.SHOTS_BASE ?? 'http://127.0.0.1:5173'
const require = createRequire(path.join(frontend, 'package.json'))
const { chromium } = require('@playwright/test')
const out = process.argv[2]
mkdirSync(out, { recursive: true })
const demo = {
  email: 'demo@example.com',
  password: process.env.RESCRIBO_DEMO_PASSWORD ?? 'Rescribo-demo-e2e-2026!',
}

const browser = await chromium.launch()
for (const scheme of ['light', 'dark']) {
  for (const [vp, size] of [['desktop', { width: 1280, height: 860 }], ['phone', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ colorScheme: scheme, viewport: size, reducedMotion: 'reduce' })
    const page = await ctx.newPage()
    const shot = async (name, settled = true) => {
      await page.waitForTimeout(400)
      await page.waitForLoadState('networkidle')
      if (settled) await page.waitForFunction(() => !document.querySelector('[data-slot="skeleton"], [aria-busy="true"]'))
      await page.screenshot({ path: path.join(out, `${name}-${vp}-${scheme}.png`), fullPage: true })
    }
    await page.goto(base + '/sign-in')
    await shot('sign-in')
    await page.getByRole('textbox', { name: 'Email' }).fill(demo.email)
    await page.getByLabel('Password').fill(demo.password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await page.waitForURL(/\/inbox$/)
    await shot('inbox')
    await page.getByRole('list', { name: 'Reports' }).getByRole('link').first().click()
    await page.waitForURL((u) => u.pathname !== '/inbox' || u.search !== '')
    await shot('inbox-report')
    await page.goto(base + '/problems')
    await shot('problems')
    await page.getByRole('link', { name: /Password reset emails/ }).first().click()
    await page.waitForURL(/\/problems\/[^/?]+$/)
    await page.getByRole('heading', { name: 'Linked reports' }).waitFor()
    await shot('problem-detail')
    await page.goto(base + '/follow-ups')
    await shot('follow-ups')
    await page.getByRole('list', { name: 'Follow-ups' }).getByRole('link').first().click()
    await page.waitForURL(/\/follow-ups\/[^/?]+/)
    await shot('follow-up-detail')
    await page.goto(base + '/follow-ups?bucket=completed')
    await shot('follow-ups-completed')
    await page.goto(base + '/settings')
    await shot('settings')
    if (vp === 'desktop') {
      await page.goto(base + '/dev/ui')
      await shot('gallery', false)
    }
    await ctx.close()
  }
}
await browser.close()
