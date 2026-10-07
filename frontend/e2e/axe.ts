import { AxeBuilder } from '@axe-core/playwright'
import type { Page } from '@playwright/test'

// A badge changing state animates its colors; axe would sample the
// mid-transition blend and report a false contrast failure.
export async function axeViolations(page: Page, rules?: string[]) {
  await page.addStyleTag({
    content:
      '*, *::before, *::after { transition: none !important; animation: none !important }',
  })
  const builder = new AxeBuilder({ page })
  if (rules) builder.withRules(rules)
  return (await builder.analyze()).violations
}
