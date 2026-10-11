# Tasks

Delivers #146. Frontend only. Do not touch the backend or `frontend/openapi.yaml`. Edit only the files named here. `frontend/src/api/request.ts` needs no change.

Do not edit `frontend/src/features/follow-ups/`, `frontend/src/features/inbox/report-actions.tsx`, or `frontend/src/features/problems/`. They get the behaviour through `fieldError` and `ActionError`.

Write the tests in group 1 first and see them fail.

## 1. Shared form layer in `frontend/src/components/forms/`

- [x] 1.1 Add `field-error.test.ts`. Use this code:

  ```ts
  import { expect, test } from 'vitest'
  import type { ApiError } from '@/api/request'
  import { fieldError, unrenderedFieldErrors } from './field-error'

  function apiError(
    fieldErrors: Record<string, string[]>,
    reason = 'invalid_request',
    detail = 'Check the submitted fields.',
  ) {
    return Object.assign(new Error(detail), {
      status: 400,
      reason,
      fieldErrors,
    }) as ApiError
  }

  test('reports a field the form never asked about', () => {
    const error = apiError({ repository: ['This field may not be blank.'] })
    expect(unrenderedFieldErrors(error)).toEqual([
      'Repository: This field may not be blank.',
    ])
  })

  test('leaves out a field the form asked about', () => {
    const error = apiError({
      channel_id: ['Too long.'],
      draft_version: ['A valid integer is required.'],
    })
    expect(fieldError(error, 'channel_id')).toBe('Too long.')
    expect(unrenderedFieldErrors(error)).toEqual([
      'Draft version: A valid integer is required.',
    ])
  })

  test('a field the form asked about counts even with no error', () => {
    const error = apiError({ title: ['Too long.'] })
    expect(fieldError(error, 'summary')).toBeUndefined()
    expect(unrenderedFieldErrors(error)).toEqual(['Title: Too long.'])
  })

  test('each failed request starts with no fields recorded', () => {
    fieldError(apiError({ title: ['Too long.'] }), 'title')
    expect(unrenderedFieldErrors(apiError({ title: ['Too long.'] }))).toEqual([
      'Title: Too long.',
    ])
  })

  test('shows an error that belongs to no field without a name', () => {
    const error = apiError({ non_field_errors: ['Expected an object.'] })
    expect(unrenderedFieldErrors(error)).toEqual(['Expected an object.'])
  })

  test('joins every message for a field', () => {
    const error = apiError({ channel_id: ['Too long.', 'Wrong pattern.'] })
    expect(unrenderedFieldErrors(error)).toEqual([
      'Channel id: Too long. Wrong pattern.',
    ])
  })

  test('puts a known code into words', () => {
    const error = apiError(
      { owner_id: ['invalid_reference'] },
      'invalid_reference',
      'Choose an existing, active record in this workspace.',
    )
    expect(unrenderedFieldErrors(error)).toEqual([
      'Owner id: Choose an active record in this workspace.',
    ])
  })

  test('adds no line for a bare reason code', () => {
    const error = apiError(
      { checked_slack: ['confirmation_required'] },
      'confirmation_required',
      'Confirm that you checked Slack before sending again.',
    )
    expect(unrenderedFieldErrors(error)).toEqual([])
  })

  test('adds no line for a message the reply already carries', () => {
    const error = apiError(
      { password: ['Password is incorrect.'] },
      'invalid_credentials',
      'Password is incorrect.',
    )
    expect(unrenderedFieldErrors(error)).toEqual([])
  })

  test('has nothing to report without field errors', () => {
    expect(unrenderedFieldErrors(new Error('Offline') as ApiError)).toEqual([])
  })
  ```

- [x] 1.2 Add `form-error-message.test.tsx`. Include a direct field query below a summary in the form JSX and a child field query rendered after the summary. Assert the direct field is omitted, and the child field message may repeat in the summary. Keep the supplied wording test. Use this base code, extended with the ordering tests:

  ```tsx
  import { render, screen } from '@testing-library/react'
  import { expect, test } from 'vitest'
  import type { ApiError } from '@/api/request'
  import { fieldError } from './field-error'
  import { Field } from './field'
  import { FormErrorMessage } from './form-error-message'

  function failure() {
    return Object.assign(new Error('Check the submitted fields.'), {
      status: 400,
      reason: 'invalid_request',
      fieldErrors: {
        email: ['Enter a valid email address.'],
        role: ['"admin" is not a valid choice.'],
      },
    }) as ApiError
  }

  // The summary sits above the field on purpose: order in the form must not matter.
  function Form({ error }: { error: ApiError }) {
    return (
      <form>
        <p role="status">
          <FormErrorMessage error={error} />
        </p>
        <Field id="email" label="Email" error={fieldError(error, 'email')} />
      </form>
    )
  }

  test('shows the message, then the fields the form does not render', () => {
    render(<Form error={failure()} />)
    const summary = screen.getByRole('status')
    expect(summary).toHaveTextContent(
      'Check the submitted fields. Role: "admin" is not a valid choice.',
    )
    expect(summary).not.toHaveTextContent('Enter a valid email address.')
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Enter a valid email address.',
    )
  })

  test('keeps the wording a summary passes in', () => {
    render(
      <p role="status">
        <FormErrorMessage
          error={failure()}
          message="Check the highlighted fields."
        />
      </p>,
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      'Check the highlighted fields. Email: Enter a valid email address. Role: "admin" is not a valid choice.',
    )
  })

  function LateField({ error }: { error: ApiError }) {
    return <Field id="email" label="Email" error={fieldError(error, 'email')} />
  }

  function FormWithLateField({ error }: { error: ApiError }) {
    return (
      <form>
        <p role="status"><FormErrorMessage error={error} /></p>
        <LateField error={error} />
      </form>
    )
  }

  test('a child field rendered after the summary may repeat its message', () => {
    render(<FormWithLateField error={failure()} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Email: Enter a valid email address.',
    )
  })
  ```

- [x] 1.3 Run `cd frontend && npx vitest run src/components/forms`. Verify: both new files fail on the missing exports, and `field.test.tsx` passes.

- [x] 1.4 Replace `field-error.ts` with this code:

  ```ts
  import type { ApiError } from '@/api/request'

  const fieldMessages: Record<string, string> = {
    invalid_reference: 'Choose an active record in this workspace.',
    title_required: 'Enter a title.',
  }

  // Fields a form asked about, per failed request. The summary reports the rest.
  const asked = new WeakMap<ApiError, Set<string>>()

  /** The first error for a form field, in words a member can act on. */
  export function fieldError(error: ApiError | null, field: string) {
    if (!error) return undefined
    let fields = asked.get(error)
    if (!fields) {
      fields = new Set()
      asked.set(error, fields)
    }
    fields.add(field)
    const message = error.fieldErrors?.[field]?.[0]
    return message ? (fieldMessages[message] ?? message) : undefined
  }

  // DRF's key for an error that belongs to no field.
  const noField = 'non_field_errors'

  function fieldLabel(field: string) {
    const words = field.replaceAll('_', ' ')
    return words.charAt(0).toUpperCase() + words.slice(1)
  }

  /** One line per field error that no `fieldError` call asked for. */
  export function unrenderedFieldErrors(error: ApiError): string[] {
    const fields = asked.get(error)
    return Object.entries(error.fieldErrors ?? {}).flatMap(
      ([field, messages]) => {
        if (fields?.has(field)) return []
        const text = messages
          .map((message) => fieldMessages[message] ?? message)
          // A bare reason code, or text the reply's message already carries.
          .filter(
            (message) => message !== error.reason && message !== error.message,
          )
          .join(' ')
        if (!text) return []
        return [field === noField ? text : `${fieldLabel(field)}: ${text}`]
      },
    )
  }
  ```

- [x] 1.5 Add `form-error-message.tsx`. Use this code:

  ```tsx
  import { Fragment } from 'react'
  import type { ApiError } from '@/api/request'
  import { unrenderedFieldErrors } from './field-error'

  /**
   * A form's failure text, then the errors for fields it does not render.
   * Direct field queries count even when this summary appears above them in JSX.
   */
  export function FormErrorMessage({
    error,
    message = error.message,
  }: {
    error: ApiError
    message?: string
  }) {
    return (
      <>
        {message}
        {unrenderedFieldErrors(error).map((line) => (
          <Fragment key={line}>
            {' '}
            <span className="block">{line}</span>
          </Fragment>
        ))}
      </>
    )
  }
  ```

- [x] 1.6 Rerun 1.3. Verify: every test in `src/components/forms` passes. If a test and the code above disagree, stop and ask. Do not change a test to fit. Run `npx prettier --write src/components/forms` so the new files match the formatter.

## 2. Shared summaries in `frontend/src/components/states/`

- [x] 2.1 `action-error.tsx`: import `FormErrorMessage` from `@/components/forms/form-error-message`. Replace `<AlertDescription>{actionMessage(error, record)}</AlertDescription>` with:

  ```tsx
  <AlertDescription>
    <FormErrorMessage error={error} message={actionMessage(error, record)} />
  </AlertDescription>
  ```

  Change nothing else in the file. If #157 has changed this file, keep its changes and apply only this edit.
- [x] 2.2 `async-states.tsx`: in `ErrorState`'s props type, change `description?: string` to `description?: ReactNode`. `ReactNode` is already imported. Change nothing else.

## 3. Forms that read `fieldErrors` directly

In each file import `fieldError` from `@/components/forms/field-error` and `FormErrorMessage` from `@/components/forms/form-error-message`. Keep every title, condition, and class as it is. Line numbers are from commit f75904d.

- [x] 3.1 `features/settings/members-settings.tsx`
  - Line 76: `error={fieldError(create.error, 'email')}`.
  - Line 85: `description={<FormErrorMessage error={create.error} />}`.
- [x] 3.2 `features/settings/confirm-action.tsx`
  - Line 67: `error={fieldError(action.error, 'confirmation')}`.
  - Line 70: `description={<FormErrorMessage error={action.error} />}`.
- [x] 3.3 `features/settings/connection-settings.tsx`
  - Line 150: `error={fieldError(setup.error, 'repository')}`.
  - Line 179: `description={<FormErrorMessage error={setup.error} />}`.
  - Line 278: `error={fieldError(action.error, 'channel_id')}`.
  - Line 293: `description={<FormErrorMessage error={action.error} />}`.
  - Leave `CheckResult` (line 336) as it is.
- [x] 3.4 `features/inbox/manual-report-page.tsx`
  - Delete the local `fieldError` closure (lines 56 to 57). In `field()`, use `error: fieldError(error, name)` from the shared module.
  - Lines 143 to 145: replace the `AlertDescription` content with

    ```tsx
    <FormErrorMessage
      error={error}
      message={`${failureMessage(error)} Your draft is kept on this page.`}
    />
    ```
- [x] 3.5 `pages/sign-in-page.tsx`
  - Lines 51 and 61: `fieldError(apiError, 'email')` and `fieldError(apiError, 'password')`.
  - Lines 63 to 67: render the alert when `apiError` is set, with `<AlertDescription><FormErrorMessage error={apiError} /></AlertDescription>`.
- [x] 3.6 `pages/reset-password-page.tsx`
  - Add `const redeemError = redeem.error as ApiError | null` beside the mutation. Import the `ApiError` type if the file lacks it.
  - Lines 84 to 91: `error={error || fieldError(redeemError, 'password')}`.
  - Line 102: `{redeemError ? <p role="alert"><FormErrorMessage error={redeemError} /></p> : null}`.
- [x] 3.7 `pages/accept-invite-page.tsx`
  - Line 122: `error={fieldError(acceptError, 'password')}`.
  - Lines 124 to 126: `{acceptError && !acceptError.fieldErrors?.password ? <p role="alert"><FormErrorMessage error={acceptError} /></p> : null}`.
  - Lines 142 and 182: `{acceptError ? <p role="alert"><FormErrorMessage error={acceptError} /></p> : null}`.
  - Lines 164 to 171: `error={passwordError || fieldError(acceptError, 'password')}`.
- [x] 3.8 Run `cd frontend && npx tsc -b && npx vitest run`. Verify: no type error and no failing test. A test that fails here is a finding. Stop and report it. Do not edit an existing test.

## 4. The original report as a test

- [x] 4.1 Add this test at the end of `features/settings/settings-page.test.tsx`. Do not change existing tests or helpers.

  ```tsx
  test.each([
    ['slack', 'Connect Slack'],
    ['github', 'Connect GitHub'],
  ] as const)(
    '%s setup shows a rejected repository where the owner can see it',
    async (provider, button) => {
      testMembership.role = 'owner'
      stubApi({
        ...unlinked,
        [`GET ${base}connections/`]: () => json([]),
        [`GET ${base}memberships/`]: () => json([]),
        [`GET ${base}invitations/`]: () => json([]),
        [`POST ${base}connections/${provider}/setup/`]: () =>
          json(
            {
              detail: 'Check the submitted fields.',
              reason: 'invalid_request',
              field_errors: { repository: ['This field may not be blank.'] },
            },
            400,
          ),
      })
      render()
      const name = provider === 'slack' ? 'Slack' : 'GitHub'
      const card = await screen.findByRole('region', { name })
      const user = userEvent.setup()
      if (provider === 'github') {
        await user.type(
          within(card).getByLabelText('GitHub repository'),
          'acme/web',
        )
      }
      await user.click(within(card).getByRole('checkbox'))
      await user.click(within(card).getByRole('button', { name: button }))
      const summary = (
        await within(card).findByText(`Could not connect ${name}`)
      ).closest('[role="alert"]')
      if (provider === 'slack') {
        expect(summary).toHaveTextContent(
          'Check the submitted fields. Repository: This field may not be blank.',
        )
      } else {
        expect(summary).not.toHaveTextContent('Repository:')
        expect(
          within(card).getAllByText('This field may not be blank.'),
        ).toHaveLength(1)
      }
    },
  )
  ```

- [x] 4.2 Run `cd frontend && npx vitest run src/features/settings/settings-page.test.tsx`. Verify: every test passes. Then prove the test can fail, in your working tree only: undo the line 179 edit from 3.3 and confirm the Slack case fails; restore it. Undo the line 150 edit and confirm the GitHub case fails on `Repository:`; restore it.

## 5. Documentation

- [x] 5.1 `frontend/DESIGN.md`, Components list: add one bullet after the `ActionError` bullet. Do not reword other lines.

  ```md
  - FormErrorMessage is the text of a form's error summary: the reply's message, then one line for each field error the form does not render. Forms read field errors through `fieldError`, which is how the summary knows what was rendered
  ```

## 6. Screenshots

- [x] 6.1 Take the after shots as `.claude/brief.md` describes, into `.claude/shots/after`.
- [x] 6.2 Run `SHOTS_BASE=http://127.0.0.1:5146 node .claude/shots/forced-field-error.mjs .claude/shots/after`. The planner used the same script for the before shots. Build `.claude/shots/compare.html` with `compare.py`.

## 7. Repository checks

- [x] 7.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 7.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. `schema-check` must report no API change.
- [x] 7.3 `RESCRIBO_E2E_API_PORT=8146 RESCRIBO_E2E_FRONTEND_PORT=5146 task e2e` passes. Record the counts for the PR.
- [x] 7.4 No dev server is left on 8146 or 5146.

## Workflow follow-up

- Archive this change in the PR that completes #146 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": the summary knows rendered fields through `fieldError` calls (D1); labels come from API keys (D2); bare reason codes add no line (D2); "Check the highlighted fields." stays as it is (D4); three settings fields show the first message only (D5); the manual report title error becomes "Enter a title." for `title_required` (D5); internal field keys can show as labels (D2); no browser test (D7).
- PR Screenshots: "Pending".
