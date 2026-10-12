import { useEffect, useRef } from 'react'

// The only place a keyboard shortcut is declared. Each one is Cmd or Ctrl plus `key`.
export const SHORTCUTS = {
  openPalette: { key: 'k', label: 'Open command palette' },
  toggleSidebar: { key: 'b', label: 'Toggle sidebar' },
} as const

export type ShortcutId = keyof typeof SHORTCUTS

const bound = new Map<ShortcutId, () => void>()

function onKeyDown(event: KeyboardEvent) {
  if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey)
    return
  const key = event.key.toLowerCase()
  const id = (Object.keys(SHORTCUTS) as ShortcutId[]).find(
    (candidate) => SHORTCUTS[candidate].key === key,
  )
  const handler = id ? bound.get(id) : undefined
  if (!handler) return
  event.preventDefault()
  handler()
}

function bind(id: ShortcutId, handler: () => void) {
  if (bound.has(id)) throw new Error(`Shortcut "${id}" is already bound`)
  if (bound.size === 0) window.addEventListener('keydown', onKeyDown)
  bound.set(id, handler)
  return () => {
    bound.delete(id)
    if (bound.size === 0) window.removeEventListener('keydown', onKeyDown)
  }
}

/** Binds the handler to the shortcut while the calling component is mounted. */
export function useShortcut(id: ShortcutId, handler: () => void) {
  const latest = useRef(handler)
  useEffect(() => {
    latest.current = handler
  })
  useEffect(() => bind(id, () => latest.current()), [id])
}

/** Runs the handler bound to the shortcut, as its keys would. */
export function runShortcut(id: ShortcutId) {
  bound.get(id)?.()
}

/** The shortcuts that have a handler now, with their labels. */
export function boundShortcuts() {
  return (Object.keys(SHORTCUTS) as ShortcutId[])
    .filter((id) => bound.has(id))
    .map((id) => ({ id, label: SHORTCUTS[id].label }))
}

const isApple = () => /^(Mac|iPhone|iPad|iPod)/.test(navigator.platform)

/** Keys to show for a shortcut: Cmd on Apple devices, Ctrl elsewhere. */
export function shortcutKeys(id: ShortcutId) {
  return [isApple() ? '⌘' : 'Ctrl', SHORTCUTS[id].key.toUpperCase()]
}
