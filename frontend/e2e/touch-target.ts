import { expect, type Locator, type Page } from '@playwright/test'

// Wait for motion to stop before measuring transformed fractional bounds.
export async function expectTouchTarget(locator: Locator) {
  await locator.evaluate(async (element) => {
    const animations = []
    for (
      let ancestor: Element | null = element;
      ancestor;
      ancestor = ancestor.parentElement
    ) {
      animations.push(...ancestor.getAnimations())
    }
    await Promise.all(animations.map((animation) => animation.finished))
  })
  const box = await locator.boundingBox()
  expect(box?.height).toBeGreaterThanOrEqual(44)
}

export async function expectVisibleControlTouchTargets(page: Page) {
  for (const control of await page
    .locator(
      'button:visible, input[data-slot="input"]:visible, select:visible, textarea:visible, label:has(input[type="checkbox"]):visible',
    )
    .all()) {
    await expectTouchTarget(control)
  }
}
