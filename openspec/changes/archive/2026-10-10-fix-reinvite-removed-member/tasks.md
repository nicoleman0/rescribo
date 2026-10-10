# Tasks

Delivers #143. Change only the files named below. Do not edit `backend/config/settings.py`, anything under `frontend/src/api/`, `frontend/openapi.yaml`, or `.claude/skills/`.

The code blocks were run against a throwaway prototype on commit b26db6e and then reverted. Use them as written. If one does not behave as its task says, stop and ask.

Ports and services are in `.claude/brief.md`: API 8143, frontend 5143. Never start or stop the shared services.

## 1. Backend: accept with the existing account's password

Write the tests first and see them fail, then make the change.

- [x] 1.1 Create `backend/tests/test_accounts_invitation_accept.py` with this content. Verify: `uv run pytest backend/tests/test_accounts_invitation_accept.py -q` reports 8 failed, 2 passed. The two that pass are `test_new_account_sets_its_name_and_password_and_spends_the_invitation` and `test_signed_in_as_the_invited_account_accepts_without_a_password`; they guard behaviour that must not change.

  ```python
  """Invitation acceptance over HTTP, for a new account and for one that already exists."""

  from typing import Any
  from uuid import uuid4

  import pytest
  from django.conf import settings as django_settings
  from django.test import Client

  from accounts.models import Invitation, Membership, User
  from accounts.services import bootstrap_owner, create_invitation, revoke_membership
  from accounts.session import SESSION_GENERATION_KEY

  pytestmark = pytest.mark.django_db

  PASSWORD = "Harbour-Copper-7628!Quilt"
  OWNER_PASSWORD = "Strong-password-928!Cedar"
  JSON = "application/json"


  @pytest.fixture(autouse=True)
  def throttle_cache(settings: Any) -> None:
      # Throttle counts in the shared Redis cache would carry over between tests and runs.
      settings.CACHES = {
          "default": {
              "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
              "LOCATION": uuid4().hex,
          }
      }


  def make_owner(slug: str = "example") -> Membership:
      return bootstrap_owner(
          email=f"owner-{slug}@example.test",
          full_name="Owner",
          password=OWNER_PASSWORD,
          workspace_name=slug.title(),
          workspace_slug=slug,
      )[2]


  def signed_in(user: User) -> Client:
      client = Client()
      client.force_login(user)
      session = client.session
      session[SESSION_GENERATION_KEY] = user.session_generation
      session.save()
      return client


  def post(client: Client, path: str, body: dict[str, Any]) -> Any:
      return client.post(path, body, content_type=JSON)


  def accept(client: Client, secret: str, **body: str) -> Any:
      return post(client, "/api/invitations/accept/", {"token": secret, **body})


  def login(client: Client, email: str, password: str) -> Any:
      return post(client, "/api/auth/login/", {"email": email, "password": password})


  def invite(owner: Membership, email: str) -> str:
      return create_invitation(actor=owner, email=email, role=Membership.Role.MEMBER)[1]


  def removed_member(owner: Membership, email: str = "back@example.test") -> User:
      user = User.objects.create_user(email=email, full_name="Back Again", password=PASSWORD)
      membership = Membership.objects.create(workspace=owner.workspace, user=user)
      revoke_membership(actor=owner, target=membership)
      user.refresh_from_db()
      return user


  def member_elsewhere(email: str = "elsewhere@example.test") -> tuple[User, Membership]:
      other_owner = make_owner("other")
      user = User.objects.create_user(email=email, full_name="Else Where", password=PASSWORD)
      Membership.objects.create(workspace=other_owner.workspace, user=user)
      return user, other_owner


  def workspace_slugs(response: Any) -> list[str]:
      return sorted(item["workspace"]["slug"] for item in response.json()["memberships"])


  def assert_unused(secret_owner: Membership, email: str) -> None:
      invitation = Invitation.objects.get(workspace=secret_owner.workspace, email=email)
      assert invitation.used_at is None and invitation.revoked_at is None


  def test_new_account_sets_its_name_and_password_and_spends_the_invitation() -> None:
      owner = make_owner()
      secret = invite(owner, "new@example.test")
      client = Client()
      response = accept(client, secret, full_name="New Person", password=PASSWORD)
      assert response.status_code == 200
      user = User.objects.get(email="new@example.test")
      assert user.full_name == "New Person" and user.check_password(PASSWORD)
      assert workspace_slugs(client.get("/api/auth/session/")) == ["example"]
      again = accept(Client(), secret, full_name="Other", password=PASSWORD)
      assert again.status_code == 400
      assert again.json()["reason"] == "invitation_already_used"


  def test_removed_member_is_invited_again_and_accepts_with_their_password() -> None:
      owner = make_owner()
      owner_client = signed_in(owner.user)
      invitations = f"/api/workspaces/{owner.workspace_id}/invitations/"
      email = "back@example.test"

      first = post(owner_client, invitations, {"email": email, "role": "member"})
      assert first.status_code == 201
      before = Client()
      joined = accept(
          before,
          first.json()["accept_url"].rsplit("/", 1)[-1],
          full_name="Back Again",
          password=PASSWORD,
      )
      assert joined.status_code == 200
      membership = Membership.objects.get(user__email=email)

      revoke = f"/api/workspaces/{owner.workspace_id}/memberships/{membership.pk}/revoke/"
      assert post(owner_client, revoke, {}).status_code == 204
      assert before.get("/api/auth/session/").status_code == 401
      # The login rule stays: an account with no active membership cannot sign in.
      assert login(Client(), email, PASSWORD).status_code == 401

      second = post(owner_client, invitations, {"email": email, "role": "member"})
      assert second.status_code == 201
      after = Client()
      response = accept(
          after,
          second.json()["accept_url"].rsplit("/", 1)[-1],
          full_name="Renamed",
          password=PASSWORD,
      )

      assert response.status_code == 200
      assert workspace_slugs(response) == ["example"]
      assert response.json()["memberships"][0]["role"] == "member"
      assert workspace_slugs(after.get("/api/auth/session/")) == ["example"]
      membership.refresh_from_db()
      assert membership.is_active and membership.revoked_at is None
      user = User.objects.get(email=email)
      assert user.full_name == "Back Again" and user.check_password(PASSWORD)
      assert not Invitation.objects.filter(email=email, used_at__isnull=True).exists()
      # The session from before the removal stays dead.
      assert before.get("/api/auth/session/").status_code == 401
      assert login(Client(), email, PASSWORD).status_code == 200


  @pytest.mark.parametrize("body", [{"password": "wrong"}, {"password": ""}, {}])
  def test_wrong_password_starts_no_session_and_keeps_the_invitation(body: dict[str, str]) -> None:
      owner = make_owner()
      user = removed_member(owner)
      secret = invite(owner, user.email)
      client = Client()

      response = accept(client, secret, **body)

      assert response.status_code == 401
      assert response.json() == {
          "detail": "Password is incorrect.",
          "reason": "invalid_credentials",
          "field_errors": {"password": ["Password is incorrect."]},
      }
      assert client.get("/api/auth/session/").status_code == 401
      assert not Membership.objects.get(user=user).is_active
      assert_unused(owner, user.email)
      assert accept(client, secret, password=PASSWORD).status_code == 200


  def test_signed_in_as_the_invited_account_accepts_without_a_password() -> None:
      owner = make_owner()
      user, _ = member_elsewhere()
      secret = invite(owner, user.email)
      password_hash = user.password
      client = signed_in(user)

      response = accept(client, secret, full_name="Renamed", password="Another-password-112!Fir")

      assert response.status_code == 200
      assert workspace_slugs(response) == ["example", "other"]
      user.refresh_from_db()
      assert user.full_name == "Else Where" and user.password == password_hash


  def test_signed_in_as_another_account_is_refused_even_with_the_password() -> None:
      owner = make_owner()
      user = removed_member(owner)
      _, other_owner = member_elsewhere()
      secret = invite(owner, user.email)
      client = signed_in(other_owner.user)

      response = accept(client, secret, password=PASSWORD)

      assert response.status_code == 400
      assert response.json()["reason"] == "sign_in_required"
      assert response.json()["detail"].startswith("This invitation is for a different account.")
      assert client.get("/api/auth/session/").json()["user"]["email"] == other_owner.user.email
      assert not Membership.objects.filter(workspace=owner.workspace, user=other_owner.user).exists()
      assert not Membership.objects.get(workspace=owner.workspace, user=user).is_active
      assert_unused(owner, user.email)


  def test_account_active_in_another_workspace_accepts_with_its_password() -> None:
      owner = make_owner()
      user, other_owner = member_elsewhere()
      secret = invite(owner, user.email)

      assert accept(Client(), secret, password="wrong").status_code == 401
      assert_unused(owner, user.email)
      response = accept(Client(), secret, password=PASSWORD)

      assert response.status_code == 200
      assert workspace_slugs(response) == ["example", "other"]
      elsewhere = Membership.objects.get(workspace=other_owner.workspace, user=user)
      assert elsewhere.is_active and elsewhere.role == Membership.Role.MEMBER


  def test_deactivated_account_is_refused_like_a_wrong_password() -> None:
      owner = make_owner()
      user = removed_member(owner)
      User.objects.filter(pk=user.pk).update(is_active=False)
      secret = invite(owner, user.email)
      client = Client()

      response = accept(client, secret, password=PASSWORD)

      assert response.status_code == 401
      assert response.json()["reason"] == "invalid_credentials"
      assert client.get("/api/auth/session/").status_code == 401
      assert_unused(owner, user.email)


  def test_password_attempts_on_an_invitation_share_the_login_limit() -> None:
      limit = int(
          django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login_identity"].split("/")[0]
      )
      owner = make_owner()
      user = removed_member(owner)
      secret = invite(owner, user.email)
      other = removed_member(owner, email="other-back@example.test")
      other_secret = invite(owner, other.email)
      client = Client()

      for _ in range(limit):
          assert accept(client, secret, password="wrong").status_code == 401

      assert accept(client, secret, password=PASSWORD).status_code == 429
      assert login(Client(), user.email, PASSWORD).status_code == 429
      assert_unused(owner, user.email)
      # The limit is per account: another invited account and another login still work.
      assert accept(client, other_secret, password=PASSWORD).status_code == 200
      assert login(Client(), owner.user.email, OWNER_PASSWORD).status_code == 200
  ```

- [x] 1.2 In `backend/accounts/services.py`, add this function directly above `accept_invitation`. Verify: `uv run ruff check backend/accounts` passes.

  ```python
  def invited_account_email(*, secret: str) -> str | None:
      """The email whose password an invitation checks, or None when it creates the account."""
      email = (
          Invitation.objects.filter(token_digest=digest(secret))
          .values_list("email", flat=True)
          .first()
      )
      if email is None or not get_user_model().objects.filter(email=email).exists():
          return None
      return email
  ```

- [x] 1.3 In `accept_invitation`, replace

  ```python
          if user is not None:
              if authenticated_user is None or authenticated_user.pk != user.pk:
                  raise TokenError("sign_in_required")
  ```

  with

  ```python
          if user is not None:
              if authenticated_user is not None:
                  if authenticated_user.pk != user.pk:
                      raise TokenError("sign_in_required")
              # Without a session, the account's password is the only proof of control.
              elif not (user.is_active and user.check_password(password)):
                  raise TokenError("invalid_credentials")
  ```

  Leave the rest of the function unchanged. Verify: `git diff backend/accounts/services.py` shows only 1.2 and this hunk.

- [x] 1.4 In `backend/accounts/throttling.py`, add `from accounts.services import invited_account_email` after the `rest_framework` imports, and replace the whole `LoginIdentityThrottle` class with the two classes below. The login cache key must stay the same value as before. Verify: `uv run mypy` reports no issues.

  ```python
  class LoginIdentityThrottle(SimpleRateThrottle):
      scope = "login_identity"

      def identity_key(self, email: str) -> str:
          return self.cache_format % {
              "scope": self.scope,
              "ident": hashlib.sha256(email.strip().lower().encode()).hexdigest(),
          }

      def get_cache_key(self, request: Request, view: APIView) -> str | None:
          payload = request.data
          return self.identity_key(str(payload.get("email", "") if isinstance(payload, dict) else ""))


  class InvitationPasswordThrottle(LoginIdentityThrottle):
      """Shares the login limit, so an invitation adds no password guesses for its account."""

      def get_cache_key(self, request: Request, view: APIView) -> str | None:
          if request.user.is_authenticated:
              return None
          payload = request.data
          secret = str(payload.get("token", "") if isinstance(payload, dict) else "")
          email = invited_account_email(secret=secret)
          return None if email is None else self.identity_key(email)
  ```

- [x] 1.5 In `backend/accounts/views.py`: import `InvitationPasswordThrottle` from `accounts.throttling`; set `throttle_classes = [TokenRedemptionThrottle, InvitationPasswordThrottle]` on `InviteAcceptView`; and in `error_response` add the lines below directly above `if reason == "password_rejected":`. Verify: the test file from 1.1 reports 10 passed.

  ```python
      if reason == "sign_in_required":
          detail = "This invitation is for a different account. Sign out, then open the link again."
      if reason == "invalid_credentials":
          detail = "Password is incorrect."
          return Response(
              {"detail": detail, "reason": reason, "field_errors": {"password": [detail]}},
              status=status.HTTP_401_UNAUTHORIZED,
          )
  ```

- [x] 1.6 Run `uv run pytest backend/tests/test_accounts_api.py backend/tests/test_accounts_services.py backend/tests/test_accounts_models.py backend/tests/test_workspace_isolation_api.py -q`, `uv run ruff check . && uv run ruff format --check .`, and `task schema-check`. Verify: all pass and `schema-check` reports no API change. If it reports a change, stop and ask; do not run `task schema`.

## 2. Invitation page

- [x] 2.1 In `frontend/src/pages/token-preview-pages.test.tsx`: in the last `test.each`, change the 401 row to `[401, 'This email already has an account', 'Accept invitation'],` and replace the `expect(screen.getByRole(status === 401 ? 'link' : 'button', ...)).toBeVisible()` statement with `expect(screen.getByRole('button', { name: actionName })).toBeVisible()`. Then add the test below at the end of the file. Verify: `cd frontend && npx vitest run src/pages/token-preview-pages.test.tsx` reports 2 failed (the 401 row and the new test) and 4 passed.

  ```tsx
  test('an existing account accepts with its password', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/auth/csrf/'))
          return Promise.resolve(new Response(null, { status: 204 }))
        if (url.includes('/invitations/preview/'))
          return Promise.resolve(
            response({ status: 'requires_sign_in', workspace_name: 'Example' }),
          )
        if (url.includes('/auth/session/'))
          return Promise.resolve(response({ detail: 'Nope' }, 401))
        if (url.includes('/invitations/accept/')) {
          bodies.push(JSON.parse(String(init?.body)))
          return Promise.resolve(
            bodies.length === 1
              ? response(
                  {
                    detail: 'Password is incorrect.',
                    reason: 'invalid_credentials',
                    field_errors: { password: ['Password is incorrect.'] },
                  },
                  401,
                )
              : response({
                  user: { id: '1', email: 'back@example.test', full_name: 'B' },
                  memberships: [],
                }),
          )
        }
        throw new Error(`Unexpected request: ${url}`)
      }),
    )
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/invite/example']}>
          <Routes>
            <Route path="/invite/:token" element={<AcceptInvitePage />} />
            <Route path="/inbox" element={<p>Inbox reached</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const password = await screen.findByLabelText('Password')
    expect(screen.getByText(/Join Example\./)).toBeVisible()
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: 'Sign in' }),
    ).not.toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Accept invitation' })
    await user.type(password, 'wrong-password')
    await user.click(submit)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Password is incorrect.',
    )
    expect(password).toHaveValue('wrong-password')
    await user.clear(password)
    await user.type(password, 'right-password')
    await user.click(submit)
    expect(await screen.findByText('Inbox reached')).toBeVisible()
    expect(bodies).toEqual([
      { token: 'example', full_name: '', password: 'wrong-password' },
      { token: 'example', full_name: '', password: 'right-password' },
    ])
    vi.unstubAllGlobals()
  })
  ```

- [x] 2.2 In `frontend/src/pages/accept-invite-page.tsx`: remove `useLocation` from the `react-router-dom` import and delete `const location = useLocation()`; add `const acceptError = accept.error as ApiError | null` directly above `function submit`; and replace the `<p>` that holds the "Sign in" link (the branch for `requires_sign_in` with no `currentSession.data`) with the block below. Do not change the other branches or the mutation. Verify: the command from 2.1 reports 6 passed, and `cd frontend && npm run typecheck && npm run lint && npx prettier --check src/pages` passes.

  ```tsx
          <>
            <p className="my-3 text-sm">
              Join {preview.data.workspace_name}. This email already has an
              account. Enter its password to accept.
            </p>
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault()
                accept.mutate()
              }}
            >
              <Field
                id="current-password"
                label="Password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                error={acceptError?.fieldErrors?.password?.[0]}
              />
              {accept.isError && !acceptError?.fieldErrors?.password ? (
                <p role="alert">{accept.error.message}</p>
              ) : null}
              <Button type="submit" disabled={accept.isPending}>
                Accept invitation
              </Button>
            </form>
          </>
  ```

## 3. Browser test

- [x] 3.1 Add this test at the end of `frontend/e2e/accounts.spec.ts`. Do not change existing tests. Verify with the API change from group 1 in place: `cd frontend && RESCRIBO_E2E_API_PORT=8143 RESCRIBO_E2E_FRONTEND_PORT=5143 npx playwright test e2e/accounts.spec.ts -g "removed member"` reports 3 passed (two setup, one test). Both variables are required; without them Playwright tests another checkout. On commit b26db6e this test times out waiting for the `Password` field, because the page shows only the sign-in link.

  ```ts
  test('a removed member accepts a new invitation with their password', async ({
    page,
    browser,
  }) => {
    const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
    const email = `reinvite-${Date.now()}@example.test`
    const password = 'Harbour-Copper-7628!Quilt'
    await page.goto('/sign-in')
    await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[3].email)
    await page.getByLabel('Password').fill(seed.users[0].password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/inbox$/)
    await page.evaluate(() => fetch('/api/auth/csrf/'))
    const csrfCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === 'csrftoken',
    )
    const workspace = `/api/workspaces/${seed.workspace_id}`
    const ownerPost = (path: string, data?: unknown) =>
      page.context().request.post(new URL(path, page.url()).toString(), {
        data,
        headers: { 'X-CSRFToken': csrfCookie?.value ?? '' },
      })
    const invite = async () => {
      const response = await ownerPost(`${workspace}/invitations/`, {
        email,
        role: 'member',
      })
      expect(response.status()).toBe(201)
      return ((await response.json()) as { accept_url: string }).accept_url
    }

    // One browser context throughout, so the second visit carries the cookie of
    // the session that the removal ended.
    const memberContext = await browser.newContext({
      baseURL: new URL(page.url()).origin,
    })
    const member = await memberContext.newPage()
    await member.goto(await invite())
    await member.getByLabel('Full name').fill('Returning Member')
    await member.getByLabel('Password', { exact: true }).fill(password)
    await member.getByLabel('Confirm password').fill(password)
    await member.getByRole('button', { name: 'Accept invitation' }).click()
    await expect(member).toHaveURL(/\/inbox$/)

    const memberships = await page
      .context()
      .request.get(`${workspace}/memberships/`)
    const rows = (await memberships.json()) as { id: string; email: string }[]
    const membership = rows.find((row) => row.email === email)
    expect(membership).toBeTruthy()
    const revoked = await ownerPost(
      `${workspace}/memberships/${membership!.id}/revoke/`,
    )
    expect(revoked.status()).toBe(204)
    await member.goto('/inbox')
    await expect(member).toHaveURL(/\/sign-in$/)

    await member.goto(await invite())
    await expect(
      member.getByText('This email already has an account.'),
    ).toBeVisible()
    await expect(member.getByLabel('Full name')).toHaveCount(0)
    await member.getByLabel('Password').fill('not-the-password')
    await member.getByRole('button', { name: 'Accept invitation' }).click()
    await expect(member.getByRole('alert')).toHaveText('Password is incorrect.')
    await expect(member).toHaveURL(/\/invite\//)
    await member.getByLabel('Password').fill(password)
    await member.getByRole('button', { name: 'Accept invitation' }).click()
    await expect(member).toHaveURL(/\/inbox$/)

    const session = await memberContext.request.get('/api/auth/session/')
    expect(session.status()).toBe(200)
    const { memberships: active } = (await session.json()) as {
      memberships: { role: string; workspace: { id: string } }[]
    }
    expect(active.map((item) => [item.workspace.id, item.role])).toEqual([
      [seed.workspace_id, 'member'],
    ])
    await member.getByRole('button', { name: 'Sign out' }).click()
    await expect(member).toHaveURL(/\/sign-in$/)
    await member.getByRole('textbox', { name: 'Email' }).fill(email)
    await member.getByLabel('Password').fill(password)
    await member.getByRole('button', { name: 'Sign in' }).click()
    await expect(member).toHaveURL(/\/inbox$/)
    await memberContext.close()
  })
  ```

- [x] 3.2 If an accept or reset step answers 429 after repeated runs, clear the address limit in this worktree's Redis index only, then rerun. Verify: the rerun passes.

  ```sh
  uv run python backend/manage.py shell -c "from django.core.cache import cache; cache.delete('throttle_token_redemption_127.0.0.1')"
  ```

## 4. Screenshots

- [x] 4.1 With the dev servers from `.claude/brief.md` running on 8143 and 5143, run `SHOTS_BASE=http://127.0.0.1:5143 node .claude/shots/invite-shots.mjs .claude/shots/after` from the worktree root. Verify: `.claude/shots/after/` holds eight PNG files with the same names as `.claude/shots/before/`, and `invite-existing-*` shows the password field.
- [x] 4.2 Write the spec below to `.claude/shots/compare-143.json` and run `python3 .claude/skills/work-issues/scripts/compare.py .claude/shots/compare-143.json .claude/shots/compare.html`. Verify: `.claude/shots/compare.html` exists and the two `invite-new-*` pairs look identical.

  ```json
  {
    "before": ".claude/shots/before",
    "after": ".claude/shots/after",
    "title": "Invitation page for an existing account (#143)",
    "heading": "Invitation page for an existing account",
    "intro": "A removed member opens a new invitation, signed out. Before: a link to a sign-in that always fails. After: a password field on the page.",
    "meta": "Issue #143",
    "screens": [
      ["invite-existing-desktop-light", "Existing account, desktop, light", "Changed"],
      ["invite-existing-desktop-dark", "Existing account, desktop, dark", "Changed"],
      ["invite-existing-phone-light", "Existing account, phone, light", "Changed"],
      ["invite-existing-phone-dark", "Existing account, phone, dark", "Changed"],
      ["invite-new-desktop-light", "New account, desktop, light", "Must not change"],
      ["invite-new-phone-dark", "New account, phone, dark", "Must not change"]
    ]
  }
  ```

## 5. Repository checks

- [x] 5.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 5.2 `task check test build schema-check` passes with PostgreSQL and Redis running. Use `task test-backend`, not a bare `uv run pytest`, for the full backend run. Record the test counts for the PR.
- [x] 5.3 `RESCRIBO_E2E_API_PORT=8143 RESCRIBO_E2E_FRONTEND_PORT=5143 task e2e` passes. Record the counts for the PR. See 3.2 for a 429.
- [x] 5.4 No dev server is left on 8143 or 5143, and `git status` shows only the files this change names.

## Workflow follow-up

- Archive this change in the PR that completes #143 (`/opsx:archive`). The archive adds one requirement to `openspec/specs/accounts/spec.md`; it must not reword existing text.
- PR body starts with `Fixes #143.` Milestone: none.
- PR "Decisions to review": the accept endpoint now checks a password and shares the login identity limit; a wrong password answers 401 `invalid_credentials`; an account active in another workspace may accept with its password; the "Sign in to accept" link is gone; the preview status keeps the name `requires_sign_in`.
- PR Screenshots: "Pending". The comparison page is `.claude/shots/compare.html`.
- Not in this change: the login error text for a non-member, and #142.
