import { AxeBuilder } from '@axe-core/playwright'
import type { Page } from '@playwright/test'

// A badge changing state animates its colors; axe would sample the
// mid-transition blend and report a false contrast failure.
export async function axeViolations(page: Page) {
  await page.addStyleTag({
    content:
      '*, *::before, *::after { transition: none !important; animation: none !important }',
  })
  return (await new AxeBuilder({ page }).analyze()).violations
}
