import { beforeEach, expect, test, vi } from 'vitest'
import {
  readSidebarOpen,
  SIDEBAR_STORAGE_KEY,
  writeSidebarOpen,
} from './sidebar-state'

beforeEach(() => {
  localStorage.clear()
})

test('defaults to expanded and persists the next state', () => {
  expect(readSidebarOpen()).toBe(true)
  writeSidebarOpen(false)
  expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('false')
  expect(readSidebarOpen()).toBe(false)
})

test('uses the in-page value when storage is blocked', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  writeSidebarOpen(false)
  expect(() => readSidebarOpen()).not.toThrow()
  expect(readSidebarOpen()).toBe(false)
})
