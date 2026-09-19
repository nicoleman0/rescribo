import { expect, test } from '@playwright/test'

test('browser reaches the real backend and dependencies through the dev proxy', async ({
  page,
}) => {
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Feedback inbox' }),
  ).toBeVisible()
  await expect(page.getByRole('status')).toHaveText(
    'API, PostgreSQL, and Redis are ready.',
  )
})
