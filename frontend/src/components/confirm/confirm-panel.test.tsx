import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { ConfirmPanel } from './confirm-panel'

function renderPanel(
  props: Partial<React.ComponentProps<typeof ConfirmPanel>> = {},
) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <ConfirmPanel
      title="Delete report?"
      description="This action is permanent."
      confirmLabel="Delete report"
      pendingLabel="Working…"
      isPending={false}
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  )
  return { onConfirm, onCancel }
}

test('renders its title at the requested heading level', () => {
  renderPanel()
  expect(
    screen.getByRole('heading', { level: 3, name: 'Delete report?' }),
  ).toBeVisible()
})

test('supports a level four title', () => {
  renderPanel({ headingLevel: 4 })
  expect(
    screen.getByRole('heading', { level: 4, name: 'Delete report?' }),
  ).toBeVisible()
})

test('disables confirm when requested or pending and disables cancel while pending', () => {
  const { rerender } = render(
    <ConfirmPanel
      title="Delete report?"
      description="This action is permanent."
      confirmLabel="Delete report"
      pendingLabel="Working…"
      isPending={false}
      confirmDisabled
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
    />,
  )
  expect(screen.getByRole('button', { name: 'Delete report' })).toBeDisabled()
  rerender(
    <ConfirmPanel
      title="Delete report?"
      description="This action is permanent."
      confirmLabel="Delete report"
      pendingLabel="Working…"
      isPending
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
    />,
  )
  expect(screen.getByRole('button', { name: 'Working…' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
})

test('submits and cancels through their callbacks', () => {
  const callbacks = renderPanel()
  fireEvent.submit(screen.getByRole('form', { name: 'Delete report?' }))
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(callbacks.onConfirm).toHaveBeenCalledOnce()
  expect(callbacks.onCancel).toHaveBeenCalledOnce()
})

test('focuses the title only when requested', () => {
  const panelProps = {
    title: 'Delete report?',
    description: 'This action is permanent.',
    confirmLabel: 'Delete report',
    pendingLabel: 'Working…',
    isPending: false,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  }
  const { unmount } = render(<ConfirmPanel {...panelProps} focusOnOpen />)
  const focusedTitle = screen.getByRole('heading', { name: 'Delete report?' })
  expect(focusedTitle).toHaveFocus()
  unmount()
  render(<ConfirmPanel {...panelProps} />)
  expect(
    screen.getByRole('heading', { name: 'Delete report?' }),
  ).not.toHaveAttribute('tabindex')
})
