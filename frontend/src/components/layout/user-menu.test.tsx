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
  localStorage.setItem('rescribo-theme', 'light')
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
  await user.click(trigger)
  expect(screen.getByRole('menuitemradio', { name: 'Dark' })).toHaveAttribute(
    'aria-checked',
    'true',
  )
})

test('marks the selected theme and calls sign out', async () => {
  const user = userEvent.setup()
  const onSignOut = vi.fn()
  localStorage.setItem('rescribo-theme', 'light')
  render(
    <UserMenu
      session={session}
      workspaceName="Northwind"
      isDemo={false}
      onSignOut={onSignOut}
    />,
  )
  const trigger = screen.getByRole('button', {
    name: /User menu for Ada Lovelace/,
  })
  trigger.focus()
  await user.keyboard('{Enter}')
  expect(
    await screen.findByRole('menuitemradio', { name: 'Dark' }),
  ).toHaveAttribute('aria-checked', 'false')
  await user.click(screen.getByRole('menuitem', { name: 'Sign out' }))
  expect(onSignOut).toHaveBeenCalledOnce()
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
