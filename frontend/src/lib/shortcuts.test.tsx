import { fireEvent, render } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import {
  boundShortcuts,
  runShortcut,
  shortcutKeys,
  useShortcut,
} from './shortcuts'

function Bind({
  id,
  handler,
}: {
  id: 'openPalette' | 'toggleSidebar'
  handler: () => void
}) {
  useShortcut(id, handler)
  return null
}

function press(init: KeyboardEventInit) {
  const event = new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    ...init,
  })
  window.dispatchEvent(event)
  return event
}

afterEach(() => vi.restoreAllMocks())

test('Ctrl+K and Cmd+K call the handler and prevent the default', () => {
  const handler = vi.fn()
  render(<Bind id="openPalette" handler={handler} />)
  expect(press({ key: 'k', ctrlKey: true }).defaultPrevented).toBe(true)
  expect(press({ key: 'K', metaKey: true }).defaultPrevented).toBe(true)
  expect(handler).toHaveBeenCalledTimes(2)
})

test('other key combinations do not call the handler', () => {
  const handler = vi.fn()
  render(<Bind id="openPalette" handler={handler} />)
  press({ key: 'k' })
  press({ key: 'k', ctrlKey: true, shiftKey: true })
  press({ key: 'k', ctrlKey: true, altKey: true })
  expect(handler).not.toHaveBeenCalled()
})

test('an unbound shortcut keeps the default', () => {
  render(<Bind id="openPalette" handler={vi.fn()} />)
  expect(press({ key: 'b', ctrlKey: true }).defaultPrevented).toBe(false)
})

test('unmounting unbinds', () => {
  const handler = vi.fn()
  const { unmount } = render(<Bind id="openPalette" handler={handler} />)
  unmount()
  expect(press({ key: 'k', ctrlKey: true }).defaultPrevented).toBe(false)
  expect(handler).not.toHaveBeenCalled()
  expect(boundShortcuts()).toEqual([])
})

test('uses the latest handler without rebinding', () => {
  const first = vi.fn()
  const second = vi.fn()
  const { rerender } = render(<Bind id="openPalette" handler={first} />)
  rerender(<Bind id="openPalette" handler={second} />)
  press({ key: 'k', ctrlKey: true })
  expect(first).not.toHaveBeenCalled()
  expect(second).toHaveBeenCalledTimes(1)
})

test('binding one id twice throws', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  expect(() =>
    render(
      <>
        <Bind id="openPalette" handler={vi.fn()} />
        <Bind id="openPalette" handler={vi.fn()} />
      </>,
    ),
  ).toThrow(/already bound/)
})

test('boundShortcuts lists only bound ids and runShortcut calls the handler', () => {
  const handler = vi.fn()
  render(<Bind id="toggleSidebar" handler={handler} />)
  expect(boundShortcuts()).toEqual([
    { id: 'toggleSidebar', label: 'Toggle sidebar' },
  ])
  runShortcut('toggleSidebar')
  expect(handler).toHaveBeenCalledTimes(1)
  fireEvent.keyDown(document.body, { key: 'b', ctrlKey: true })
  expect(handler).toHaveBeenCalledTimes(2)
})

test('shortcutKeys shows Cmd on Apple platforms and Ctrl elsewhere', () => {
  const platform = vi.spyOn(navigator, 'platform', 'get')
  platform.mockReturnValue('MacIntel')
  expect(shortcutKeys('openPalette')).toEqual(['⌘', 'K'])
  platform.mockReturnValue('Win32')
  expect(shortcutKeys('openPalette')).toEqual(['Ctrl', 'K'])
})
