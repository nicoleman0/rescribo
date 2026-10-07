import { useSyncExternalStore } from 'react'

// Each theme needs a matching [data-theme] token block in styles/theme.css.
export const THEMES = ['light', 'dark'] as const
export type Theme = (typeof THEMES)[number]
export type ThemePreference = Theme | 'system'

// index.html repeats this key and the system rule to set the theme before first paint.
export const THEME_STORAGE_KEY = 'rescribo-theme'
const darkQuery = '(prefers-color-scheme: dark)'

const isPreference = (value: unknown): value is ThemePreference =>
  value === 'system' || THEMES.includes(value as Theme)

// Holds the choice for this page load when storage is blocked.
let unsaved: ThemePreference | null = null

export function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isPreference(stored) ? stored : 'system'
  } catch {
    return unsaved ?? 'system'
  }
}

export function resolveTheme(preference: ThemePreference): Theme {
  if (preference !== 'system') return preference
  return window.matchMedia(darkQuery).matches ? 'dark' : 'light'
}

function apply() {
  document.documentElement.dataset.theme = resolveTheme(readPreference())
}

const listeners = new Set<() => void>()
const notify = () => {
  apply()
  listeners.forEach((listener) => listener())
}

export function setPreference(preference: ThemePreference) {
  try {
    if (preference === 'system') localStorage.removeItem(THEME_STORAGE_KEY)
    else localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    unsaved = preference
  }
  notify()
}

/** Applies the saved theme and follows system and other-tab changes. */
export function startTheme() {
  apply()
  const media = window.matchMedia(darkQuery)
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_STORAGE_KEY) notify()
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
