import { useSyncExternalStore } from 'react'

// Each theme needs a matching [data-theme] token block in styles/theme.css.
export const THEMES = ['light', 'dark'] as const
export type Theme = (typeof THEMES)[number]
export type ThemePreference = Theme | 'system'

// Each palette needs light and dark [data-palette] blocks in styles/theme.css.
export const PALETTES = ['indigo', 'forest', 'autumn', 'sky'] as const
export type Palette = (typeof PALETTES)[number]

// index.html repeats this key and the palette list to set the palette before first paint.
export const PALETTE_STORAGE_KEY = 'rescribo-palette'

// index.html repeats this key and the system rule to set the theme before first paint.
export const THEME_STORAGE_KEY = 'rescribo-theme'
const darkQuery = '(prefers-color-scheme: dark)'

/** A browser-saved choice. The default is stored as no key at all. */
function createStore<T extends string>(
  key: string,
  values: readonly T[],
  fallback: T,
) {
  // Holds the choice for this page load when storage is blocked.
  let unsaved: T | null = null
  return {
    read(): T {
      try {
        const stored = localStorage.getItem(key)
        return values.includes(stored as T) ? (stored as T) : fallback
      } catch {
        return unsaved ?? fallback
      }
    },
    write(value: T) {
      try {
        if (value === fallback) localStorage.removeItem(key)
        else localStorage.setItem(key, value)
      } catch {
        unsaved = value
      }
    },
  }
}

const themeStore = createStore<ThemePreference>(
  THEME_STORAGE_KEY,
  [...THEMES, 'system'],
  'system',
)

export const readPreference = themeStore.read

const paletteStore = createStore<Palette>(
  PALETTE_STORAGE_KEY,
  PALETTES,
  'indigo',
)

export const readPalette = paletteStore.read

export function resolveTheme(preference: ThemePreference): Theme {
  if (preference !== 'system') return preference
  return window.matchMedia(darkQuery).matches ? 'dark' : 'light'
}

function apply() {
  const { dataset } = document.documentElement
  dataset.theme = resolveTheme(readPreference())
  dataset.palette = readPalette()
}

const listeners = new Set<() => void>()
const notify = () => {
  apply()
  listeners.forEach((listener) => listener())
}

export function setPreference(preference: ThemePreference) {
  themeStore.write(preference)
  notify()
}

export function setPalette(palette: Palette) {
  paletteStore.write(palette)
  notify()
}

/** Applies the saved theme and palette and follows system and other-tab changes. */
export function startTheme() {
  apply()
  const media = window.matchMedia(darkQuery)
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_STORAGE_KEY || event.key === PALETTE_STORAGE_KEY)
      notify()
  }
  media.addEventListener('change', notify)
  window.addEventListener('storage', onStorage)
  return () => {
    media.removeEventListener('change', notify)
    window.removeEventListener('storage', onStorage)
  }
}

const subscribe = (listener: () => void) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useThemePreference() {
  const preference = useSyncExternalStore(subscribe, readPreference)
  return [preference, setPreference] as const
}

export function usePalettePreference() {
  const palette = useSyncExternalStore(subscribe, readPalette)
  return [palette, setPalette] as const
}
