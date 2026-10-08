import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import type { EngineeringIssue } from '@/api/github-issues'
import type { ProblemDetail } from '@/api/problems'
import { ProblemNextStep } from './problem-next-step'

const problem: ProblemDetail = {
  id: 'prob-1',
  title: 'Exports fail',
  summary: '',
  state: 'open',
  owner: null,
  report_count: 1,
  needs_review: false,
  resolution_revision: 0,
  fix_note: '',
  fix_version: '',
  fix_evidence_url: '',
  fix_confirmed_at: null,
  fix_confirmed_by: null,
  version: 1,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
  engineering_issue: null,
  current_create_operation: null,
}

const issue = {
  number: 42,
  url: 'https://github.com/acme/widgets/issues/42',
} as EngineeringIssue

function renderStep(changes: Partial<ProblemDetail>) {
  render(
    <MemoryRouter>
      <ProblemNextStep problem={{ ...problem, ...changes }} />
    </MemoryRouter>,
  )
  const heading = screen.getByRole('heading', { level: 2 })
  return {
    heading: heading.textContent,
    tone: heading.closest('[data-tone]')?.getAttribute('data-tone'),
    links: screen.queryAllByRole('link').map((link) => link.textContent),
  }
}

test.each([
  [{ state: 'open' }, 'info', 'Confirm the fix when it ships', []],
  [{ state: 'in_progress' }, 'progress', 'Confirm the fix when it ships', []],
  [
    { state: 'in_progress', needs_review: true, engineering_issue: issue },
    'warning',
    'Review the fix',
    ['Open follow-ups', 'Open GitHub issue #42 (opens in a new tab)'],
  ],
  [
    { state: 'fix_available', fix_version: '4.13' },
    'success',
    'Fix available in 4.13',
    ['Open follow-ups'],
  ],
  [
    { state: 'fix_available', needs_review: true },
    'warning',
    'Review the fix',
    ['Open follow-ups'],
  ],
  [{ state: 'not_planned' }, 'neutral', 'Not planned', []],
] as const)('%j shows the %s tone', (changes, tone, heading, links) => {
  expect(renderStep(changes)).toEqual({ tone, heading, links })
})

test('a fix that needs review says what to check', () => {
  renderStep({ state: 'fix_available', needs_review: true })
  expect(
    screen.getByText(/Check the follow-up outcomes and the GitHub issue/),
  ).toBeInTheDocument()
})
