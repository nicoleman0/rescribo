export const SIDEBAR_STORAGE_KEY = 'rescribo-sidebar'

let unsaved: boolean | null = null

export function readSidebarOpen() {
  try {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY)
    if (stored === 'true') return true
    if (stored === 'false') return false
    return true
  } catch {
    return unsaved ?? true
  }
}

export function writeSidebarOpen(open: boolean) {
  unsaved = open
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(open))
  } catch {
    // Keep the current page usable when browser storage is blocked.
  }
}
