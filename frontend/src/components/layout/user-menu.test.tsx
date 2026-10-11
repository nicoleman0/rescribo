import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import type { Session } from '@/api/auth'
import { UserMenu } from './user-menu'

const session: Session = {
  user: { id: 'u-1', full_name: 'Ada Lovelace', email: 'ada@example.test' },
  memberships: [],
}

test('shows identity, theme choices, and sign out in the menu', async () => {
  const user = userEvent.setup()
  render(
    <UserMenu
      session={session}
      workspaceName="Northwind"
      isDemo={false}
      onSignOut={vi.fn()}
    />,
  )
  const trigger = screen.getByRole('button', {
    name: /User menu for Ada Lovelace/,
  })
  trigger.focus()
  await user.keyboard('{Enter}')
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(await screen.findByText('ada@example.test')).toBeInTheDocument()
  expect(screen.getByRole('group', { name: 'Theme' })).toBeInTheDocument()
  expect(screen.getByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(trigger).toHaveFocus()
  await user.keyboard('{Enter}')
  await user.click(screen.getByRole('menuitemradio', { name: 'Dark' }))
  expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
})

test('shows the demo notice only for demo workspaces', async () => {
  const user = userEvent.setup()
  const view = render(
    <UserMenu
      session={session}
      workspaceName="Northwind"
      isDemo
      onSignOut={vi.fn()}
    />,
  )
  const trigger = screen.getByRole('button', {
    name: /User menu for Ada Lovelace/,
  })
  trigger.focus()
  await user.keyboard('{Enter}')
  expect(
    await screen.findByText(
      'Fictitious data. Nothing is sent to Slack or GitHub.',
    ),
  ).toBeInTheDocument()
  view.rerender(
    <UserMenu
      session={session}
      workspaceName="Northwind"
      isDemo={false}
      onSignOut={vi.fn()}
    />,
  )
  expect(
    screen.queryByText('Fictitious data. Nothing is sent to Slack or GitHub.'),
  ).not.toBeInTheDocument()
})
