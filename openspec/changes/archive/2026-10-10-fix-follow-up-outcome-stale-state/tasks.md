# Tasks

Delivers #153. Bug fix; `skip_specs: true`. Change only the files named below. Do not touch the backend, `frontend/openapi.yaml`, or anything owned by #154, #157, #158, #159, #160.

Write the tests first (groups 1 and 2) and see them fail, then make the fix (group 3).

## 1. Component tests in `frontend/src/features/follow-ups/follow-up-detail.test.tsx`

Add everything at the end of the file. Reuse the existing `base`, `csrfPath`, `ada`, `grace`, `routes`, `detail`, and `notification`. No new imports are needed. Do not change existing tests.

- [x] 1.1 Add the helpers. Use this code:

  ```tsx
  type OutcomeState = FollowUpDetail['outcome']['state']

  function outcomeDetail(state: OutcomeState, version: number) {
    return detail({
      notification: notification('sent'),
      outcome:
        state === 'pending'
          ? { state, note: '', at: null, by: null }
          : { state, note: '', at: '2026-09-20T10:00:01Z', by: ada },
      version,
    })
  }

  // A follow-up the stubbed API keeps between requests: each outcome request
  // moves it to the requested state and the next version. Returns the bodies.
  function stubOutcomes(state: OutcomeState, version: number) {
    document.cookie = 'csrftoken=csrf-token'
    let current = outcomeDetail(state, version)
    const bodies: Record<string, unknown>[] = []
    const reply = (_url: URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as {
        state: OutcomeState
        expected_version: number
      }
      bodies.push(body)
      current = outcomeDetail(body.state, body.expected_version + 1)
      return json(current)
    }
    stubApi({
      [csrfPath]: () => new Response(null, { status: 204 }),
      [`GET ${base}/`]: () => json(current),
      [`POST ${base}/outcome/`]: reply,
      [`POST ${base}/outcome/correct/`]: reply,
      'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
    })
    return bodies
  }

  const outcomeSelect = () =>
    screen.getByRole('combobox', { name: 'Record outcome' })
  const noteBox = () => screen.getByRole('textbox', { name: 'Note' })
  const reasonBox = () => screen.getByRole('textbox', { name: 'Reason' })
  ```

- [x] 1.2 Add the test for the issue's path. Use this code:

  ```tsx
  test('records contact and then confirmation without a reload', async () => {
    const bodies = stubOutcomes('pending', 1)
    renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
    await screen.findByRole('combobox', { name: 'Record outcome' })
    fireEvent.change(noteBox(), { target: { value: 'Called Acme' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
    expect(await screen.findByText('Outcome: Contacted.')).toBeVisible()
    expect(outcomeSelect()).toHaveValue('confirmed')
    fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies).toEqual([
      { state: 'contacted', note: 'Called Acme', expected_version: 1 },
      { state: 'confirmed', note: '', expected_version: 2 },
    ])
  })
  ```

- [x] 1.3 Add the two correction tests. Use this code:

  ```tsx
  test('records an outcome after a correction back to pending', async () => {
    const bodies = stubOutcomes('confirmed', 2)
    renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
    await screen.findByRole('form', { name: 'Correct outcome' })
    fireEvent.change(reasonBox(), { target: { value: 'Recorded by mistake' } })
    fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
    expect(await screen.findByText('Outcome: Pending.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies[1]).toEqual({
      state: 'contacted',
      note: '',
      expected_version: 3,
    })
  })

  test('corrects an outcome twice without a reload', async () => {
    const bodies = stubOutcomes('confirmed', 2)
    renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
    await screen.findByRole('form', { name: 'Correct outcome' })
    const correctTo = () => screen.getByRole('combobox', { name: 'Correct to' })
    fireEvent.change(correctTo(), { target: { value: 'still_affected' } })
    fireEvent.change(noteBox(), { target: { value: 'Export still fails' } })
    fireEvent.change(reasonBox(), { target: { value: 'First reason' } })
    fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
    expect(await screen.findByText('Outcome: Still affected.')).toBeVisible()
    expect(correctTo()).toHaveValue('pending')
    expect(reasonBox()).toHaveValue('')
    fireEvent.change(reasonBox(), { target: { value: 'Second reason' } })
    fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies[1]).toEqual({
      state: 'pending',
      note: '',
      reason: 'Second reason',
      expected_version: 3,
    })
  })
  ```

- [x] 1.4 Add the conflict test. Use this code:

  ```tsx
  test('keeps the note when another member changed the outcome first', async () => {
    document.cookie = 'csrftoken=csrf-token'
    let current = outcomeDetail('pending', 1)
    const bodies: Record<string, unknown>[] = []
    stubApi({
      [csrfPath]: () => new Response(null, { status: 204 }),
      [`GET ${base}/`]: () => json(current),
      [`POST ${base}/outcome/`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        if (bodies.length === 1) {
          // Another member recorded contact first.
          current = outcomeDetail('contacted', 2)
          return json(
            {
              detail: 'The follow-up changed.',
              reason: 'version_conflict',
              current,
            },
            409,
          )
        }
        current = outcomeDetail('confirmed', 3)
        return json(current)
      },
      'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
    })
    renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
    await screen.findByRole('combobox', { name: 'Record outcome' })
    // An explicit choice, which the conflict then removes from the list.
    fireEvent.change(outcomeSelect(), { target: { value: 'contacted' } })
    fireEvent.change(noteBox(), { target: { value: 'Left a voicemail' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
    expect(await screen.findByText('Outcome: Contacted.')).toBeVisible()
    expect(screen.getByText('The outcome was not recorded')).toBeVisible()
    expect(outcomeSelect()).toHaveValue('confirmed')
    expect(noteBox()).toHaveValue('Left a voicemail')
    fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies[1]).toEqual({
      state: 'confirmed',
      note: 'Left a voicemail',
      expected_version: 2,
    })
  })
  ```

- [x] 1.5 Run `cd frontend && npx vitest run src/features/follow-ups/follow-up-detail.test.tsx`. Verify: 4 failed, 21 passed. The failures are:
  - "records contact and then confirmation": second body is `state: "contacted", note: "Called Acme"`.
  - "after a correction back to pending": `state: "pending"`.
  - "corrects an outcome twice": the reason box holds `First reason`.
  - "keeps the note": second body is `state: "contacted"`.

  Run `npx prettier --check src/features/follow-ups/follow-up-detail.test.tsx` and fix formatting with `--write` if it warns.

## 2. Browser test in `frontend/e2e/follow-ups.spec.ts`

- [x] 2.1 Add this test inside `test.describe('Follow-ups', ...)`, directly before `test('marks a problem reviewed after a customer is still affected', ...)`. Do not change existing tests or helpers.

  ```ts
  test('records contact and then confirmation without touching the form again', async ({
    page,
  }) => {
    await ensureFollowUpOwner(page)
    const marker = `Second outcome ${Date.now()}`
    const title = await confirmFix(page, marker)
    await openFollowUp(page, title)
    // The contact section appears once the message is prepared. Nothing is sent.
    await detail(page).getByRole('button', { name: 'Prepare message' }).click()
    await expect(
      detail(page).getByRole('textbox', { name: 'Message' }),
    ).toBeVisible()
    const contact = page.getByRole('region', { name: 'Customer contact' })
    const record = contact.getByRole('button', { name: 'Record outcome' })
    await contact.getByLabel('Note').fill('Called the customer')
    await record.click()
    await expect(contact).toContainText('Outcome: Contacted.')
    await expect(contact.getByLabel('Record outcome')).toHaveValue('confirmed')
    // No selectOption: the form must send the option the dropdown shows.
    const [request] = await Promise.all([
      page.waitForRequest(
        (sent) => sent.method() === 'POST' && sent.url().endsWith('/outcome/'),
      ),
      record.click(),
    ])
    expect(request.postDataJSON()).toMatchObject({
      state: 'confirmed',
      note: '',
    })
    await expect(contact).toContainText('Outcome: Confirmed.')
  })
  ```

- [x] 2.2 Run `cd frontend && RESCRIBO_E2E_API_PORT=8153 RESCRIBO_E2E_FRONTEND_PORT=5153 npx playwright test e2e/follow-ups.spec.ts -g "without touching the form again"`. Verify: the new test fails with `state: "contacted", note: "Called the customer"`. Both variables are required; without them Playwright tests another checkout. Playwright starts and stops the servers itself.

## 3. Fix in `frontend/src/features/follow-ups/follow-up-detail.tsx`

Change `RecordOutcomeForm` and `CorrectionForm` only. Leave `ContactSection`, `choicesFor`, and `RecipientForm` unchanged.

- [x] 3.1 In `RecordOutcomeForm`, replace

  ```tsx
  const [state, setState] = useState<FollowUpContactState>(
    choices[0]?.value ?? 'pending',
  )
  ```

  with

  ```tsx
  const [choice, setChoice] = useState<FollowUpContactState | null>(null)
  ```

- [x] 3.2 In `RecordOutcomeForm`, pass a third argument to `useFollowUpMutation`, after the function that calls `recordFollowUpOutcome`:

  ```tsx
    () => {
      setChoice(null)
      setNote('')
    },
  ```

- [x] 3.3 In `RecordOutcomeForm`, directly after the `if (!choices.length) { ... }` block and before `function submit`, add:

  ```tsx
  // The choices change with the outcome. Send only one that is offered.
  const state = (choices.find((item) => item.value === choice) ?? choices[0])
    .value
  ```

  In the "Record outcome" `SelectField`, change `setState(` to `setChoice(` in `onChange`. Everything else that reads `state` stays as it is.

- [x] 3.4 In `CorrectionForm`, replace

  ```tsx
  const [state, setState] = useState<FollowUpContactState>(choices[0])
  ```

  with

  ```tsx
  const [choice, setChoice] = useState<FollowUpContactState | null>(null)
  // The choices change with the outcome. Send only one that is offered.
  const state = choice && choices.includes(choice) ? choice : choices[0]
  ```

- [x] 3.5 In `CorrectionForm`, pass a third argument to `useFollowUpMutation`, after the function that calls `correctFollowUpOutcome`:

  ```tsx
    () => {
      setChoice(null)
      setNote('')
      setReason('')
    },
  ```

  In the "Correct to" `SelectField`, change `setState(` to `setChoice(` in `onChange`.

- [x] 3.6 Verify: `git diff --stat frontend/src/features/follow-ups/follow-up-detail.tsx` shows 18 insertions and 6 deletions, no `setState` remains in the two forms, and `cd frontend && npx prettier --check src/features/follow-ups/follow-up-detail.tsx && npm run typecheck` passes.
- [x] 3.7 Rerun 1.5. Verify: 25 passed.
- [x] 3.8 Rerun 2.2. Verify: 1 passed (plus setup).

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. `schema-check` must report no API change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8153 RESCRIBO_E2E_FRONTEND_PORT=5153 task e2e` passes. Record the counts for the PR.
- [x] 4.4 No dev server is left on 8153 or 5153.

## Workflow follow-up

- Archive this change in the PR that completes #153 (`/opsx:archive`).
- PR milestone: none.
- PR "Decisions to review": the forms reset on the member's own save instead of on every outcome change, so a conflict keeps the note; `CorrectionForm` was stale too and is fixed here; a conflict that moves the outcome to a terminal state hides the record form with its error and note (existing behaviour, not changed).
- PR Screenshots: "Not applicable: no visible change".
