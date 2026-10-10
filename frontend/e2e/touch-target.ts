import { expect, type Locator } from '@playwright/test'

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
