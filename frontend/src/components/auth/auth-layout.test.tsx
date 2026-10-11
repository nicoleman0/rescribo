import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { AuthLayout } from './auth-layout'

test('shows the shared brand and page heading', () => {
  render(
    <AuthLayout title="Sign in">
      <form aria-label="Sign-in form" />
    </AuthLayout>,
  )
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sign in')
  expect(screen.getByRole('img', { name: 'rescribo' })).toBeVisible()
  expect(
    screen.getByText('Customer feedback. Engineering work. Follow-up.'),
  ).toBeVisible()
  expect(document.querySelector('title')).toHaveTextContent(
    'Sign in · Rescribo',
  )
})

test('places an optional subtitle close below the heading', () => {
  render(
    <AuthLayout title="Sign in" subtitle="Use your workspace account.">
      <form aria-label="Sign-in form" />
    </AuthLayout>,
  )
  expect(screen.getByRole('heading', { level: 1 })).toHaveClass('mb-1')
  expect(screen.getByText('Use your workspace account.')).toHaveClass('mb-6')
})
