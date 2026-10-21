/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import {
  PALETTES,
  PALETTE_STORAGE_KEY,
  THEME_STORAGE_KEY,
  THEMES,
  readPalette,
  readPreference,
  resolveTheme,
  setPalette,
  setPreference,
  startTheme,
  usePalettePreference,
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
  delete document.documentElement.dataset.palette
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

const runBoot = () => {
  const html = readFileSync('index.html', 'utf8')
  const boot = html.match(/<script id="theme-boot">([\s\S]*?)<\/script>/)?.[1]
  expect(boot).toBeTruthy()
  new Function(boot!)()
}

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

const block = (selector: RegExp) =>
  new Map(
    [
      ...(themeCss.match(selector)?.[1] ?? '').matchAll(
        /(--[\w-]+):\s*([^;]+);/g,
      ),
    ].map((match) => [match[1], match[2].trim()]),
  )

const themeBlocks = () => [
  block(/^:root \{([^}]*)\}/m),
  ...THEMES.filter((theme) => theme !== 'light').map((theme) =>
    block(new RegExp(`:root\\[data-theme='${theme}'\\] \\{([^}]*)\\}`)),
  ),
]

test('every theme block defines every colour token the light theme does', () => {
  const blocks = themeBlocks()
  const light = blocks[0]
  const colourTokens = [...light.keys()].filter((token) => {
    const value = light.get(token) ?? ''
    return /#|rgb|oklch|var\(--border\)/.test(value)
  })
  expect(colourTokens.length).toBeGreaterThan(30)
  for (const tokens of blocks.slice(1)) {
    expect(colourTokens.filter((token) => !tokens.has(token))).toEqual([])
  }
})

const escapeRegExp = (text: string) =>
  text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// The selector list that opens a palette block, as written in theme.css.
const paletteSelector = (palette: string, theme: string) => {
  const root = theme === 'dark' ? ":root[data-theme='dark']" : ':root'
  const own =
    palette === 'indigo'
      ? root
      : theme === 'dark'
        ? ":root[data-theme='dark'][data-palette='" + palette + "']"
        : ":root[data-palette='" + palette + "']"
  const inner = `${root} [data-palette='${palette}']`
  return new RegExp(
    `^${escapeRegExp(own)},\\n${escapeRegExp(inner)} \\{([^}]*)\\}`,
    'm',
  )
}

test('every palette has a light and a dark block that set all four variables', () => {
  const paletteVariables = [
    '--brand-hue',
    '--brand-chroma',
    '--brand-lightness',
    '--neutral-tint',
  ]
  for (const palette of PALETTES) {
    for (const theme of THEMES) {
      const tokens = block(paletteSelector(palette, theme))
      expect(
        paletteVariables.filter((token) => !tokens.has(token)),
        `${palette} ${theme}`,
      ).toEqual([])
    }
  }
})

test('palette variables live only in palette blocks', () => {
  for (const tokens of themeBlocks()) {
    expect([...tokens.keys()].filter((t) => t.startsWith('--brand-'))).toEqual(
      [],
    )
  }
})

test('status tones and destructive are fixed values', () => {
  for (const tokens of themeBlocks()) {
    const fixedTokens = [...tokens.keys()].filter(
      (token) => token.startsWith('--tone-') || token === '--destructive',
    )
    expect(fixedTokens.length).toBeGreaterThan(0)
    for (const token of fixedTokens) {
      expect(tokens.get(token), token).toMatch(/^#[0-9a-f]{6}$/)
    }
  }
})

test('falls back to indigo for a missing or unknown stored palette', () => {
  expect(readPalette()).toBe('indigo')
  localStorage.setItem(PALETTE_STORAGE_KEY, 'neon')
  expect(readPalette()).toBe('indigo')
  localStorage.setItem(PALETTE_STORAGE_KEY, 'forest')
  expect(readPalette()).toBe('forest')
})

test('stores a palette, removes the key for indigo, and applies it', () => {
  setPalette('sky')
  expect(localStorage.getItem(PALETTE_STORAGE_KEY)).toBe('sky')
  expect(document.documentElement.dataset.palette).toBe('sky')
  setPalette('indigo')
  expect(localStorage.getItem(PALETTE_STORAGE_KEY)).toBeNull()
  expect(document.documentElement.dataset.palette).toBe('indigo')
})

test('follows a palette change from another tab', () => {
  const stop = startTheme()
  expect(document.documentElement.dataset.palette).toBe('indigo')
  localStorage.setItem(PALETTE_STORAGE_KEY, 'autumn')
  window.dispatchEvent(
    new StorageEvent('storage', { key: PALETTE_STORAGE_KEY }),
  )
  expect(document.documentElement.dataset.palette).toBe('autumn')
  stop()
})

test('keeps the palette for the page when storage is blocked', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const { result } = renderHook(() => usePalettePreference())
  act(() => result.current[1]('forest'))
  expect(result.current[0]).toBe('forest')
  expect(document.documentElement.dataset.palette).toBe('forest')
})

test.each([null, 'light', 'dark', 'system', 'sepia'])(
  'the index.html boot script agrees with the module for theme %s',
  (stored) => {
    for (const dark of [false, true]) {
      systemDark = dark
      localStorage.clear()
      if (stored) localStorage.setItem(THEME_STORAGE_KEY, stored)
      runBoot()
      expect(document.documentElement.dataset.theme).toBe(
        resolveTheme(readPreference()),
      )
    }
  },
)

test.each([null, ...PALETTES, 'neon'])(
  'the index.html boot script agrees with the module for palette %s',
  (stored) => {
    if (stored) localStorage.setItem(PALETTE_STORAGE_KEY, stored)
    runBoot()
    expect(document.documentElement.dataset.palette).toBe(readPalette())
  },
)
