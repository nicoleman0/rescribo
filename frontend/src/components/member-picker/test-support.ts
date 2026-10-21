import { vi } from 'vitest'

/** jsdom lacks what cmdk and Radix Popover read. Call in `beforeEach`. */
export function stubPickerDom() {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  Element.prototype.scrollIntoView = () => {}
}
