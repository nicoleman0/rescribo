/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import {
  THEMES,
  THEME_STORAGE_KEY,
  readPreference,
  resolveTheme,
  setPreference,
  startTheme,
  useThemePreference,
} from './theme'

// Vitest blanks CSS imports, so read the stylesheet from disk (cwd is frontend/).
const themeCss = readFileSync('src/styles/theme.css', 'utf8')

let systemDark = false
let changeListeners: Array<() => void> = []

beforeEach(() => {
  systemDark = false
  changeListeners = []
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.stubGlobal('matchMedia', (query: string) => ({
    get matches() {
      return query === '(prefers-color-scheme: dark)' && systemDark
    },
    addEventListener: (_: string, listener: () => void) =>
      changeListeners.push(listener),
    removeEventListener: () => undefined,
  }))
})

afterEach(() => {
  vi.restoreAllMocks()
})

const setSystemDark = (dark: boolean) => {
  systemDark = dark
  changeListeners.forEach((listener) => listener())
}

test('falls back to system for missing or unknown stored values', () => {
  expect(readPreference()).toBe('system')
  localStorage.setItem(THEME_STORAGE_KEY, 'sepia')
  expect(readPreference()).toBe('system')
  localStorage.setItem(THEME_STORAGE_KEY, 'dark')
  expect(readPreference()).toBe('dark')
})

test('resolves system from the colour scheme preference', () => {
  expect(resolveTheme('system')).toBe('light')
  systemDark = true
  expect(resolveTheme('system')).toBe('dark')
  expect(resolveTheme('light')).toBe('light')
})

test('applies the saved theme and follows system changes live', () => {
  const stop = startTheme()
  expect(document.documentElement.dataset.theme).toBe('light')
  setSystemDark(true)
  expect(document.documentElement.dataset.theme).toBe('dark')
  setPreference('light')
  setSystemDark(true)
  expect(document.documentElement.dataset.theme).toBe('light')
  stop()
})

test('stores a choice and clears it for system', () => {
  setPreference('dark')
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
  setPreference('system')
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  expect(document.documentElement.dataset.theme).toBe('light')
})

test('keeps the choice for the page when storage is blocked', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const { result } = renderHook(() => useThemePreference())
  act(() => result.current[1]('dark'))
  expect(result.current[0]).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
})

test('every theme block defines every colour token the light theme does', () => {
  const block = (selector: RegExp) =>
    new Set(
      [...(themeCss.match(selector)?.[1] ?? '').matchAll(/(--[\w-]+):/g)].map(
        (m) => m[1],
      ),
    )
  const light = block(/^:root \{([^}]*)\}/m)
  const colourTokens = [...light].filter((token) => {
    const value = themeCss.match(new RegExp(`${token}:\\s*([^;]+);`))?.[1] ?? ''
    return /#|rgb|var\(--border\)/.test(value)
  })
  expect(colourTokens.length).toBeGreaterThan(30)
  for (const theme of THEMES.filter((t) => t !== 'light')) {
    const tokens = block(
      new RegExp(`:root\\[data-theme='${theme}'\\] \\{([^}]*)\\}`),
    )
    expect(colourTokens.filter((token) => !tokens.has(token))).toEqual([])
  }
})

test.each([null, 'light', 'dark', 'system'])(
  'the index.html boot script agrees with the module for %s',
  (stored) => {
    const html = readFileSync('index.html', 'utf8')
    const boot = html.match(/<script id="theme-boot">([\s\S]*?)<\/script>/)?.[1]
    expect(boot).toBeTruthy()
    for (const dark of [false, true]) {
      systemDark = dark
      localStorage.clear()
      if (stored) localStorage.setItem(THEME_STORAGE_KEY, stored)
      new Function(boot!)()
      expect(document.documentElement.dataset.theme).toBe(
        resolveTheme(readPreference()),
      )
    }
  },
)
