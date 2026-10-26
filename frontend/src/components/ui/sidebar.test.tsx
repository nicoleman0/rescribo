import { render, screen } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { Sidebar, SidebarProvider, SidebarRail } from './sidebar'

beforeEach(() => {
  // jsdom has no matchMedia; useIsMobile needs it.
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
})

test('the sidebar rail gates its transition for reduced motion', () => {
  render(
    <SidebarProvider>
      <Sidebar>
        <SidebarRail />
      </Sidebar>
    </SidebarProvider>,
  )
  const rail = screen.getByRole('button', { name: 'Toggle Sidebar' })
  expect(rail).toHaveClass('motion-safe:transition-all')
  expect(rail).not.toHaveClass('transition-all')
})
