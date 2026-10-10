# Tasks

Delivers #142. Change only the files named below. Do not edit `backend/config/settings.py`, `frontend/src/pages/reset-password-page.tsx`, anything under `frontend/src/api/`, `frontend/openapi.yaml`, or `.claude/skills/`.

The code blocks were run against a throwaway prototype on commit 65232e7 and then reverted. Use them as written. If one does not behave as its task says, stop and ask.

Ports and services are in `.claude/brief.md`: API 8142, frontend 5142. Never start or stop the shared services.

## 1. Refuse the current password

Write the tests first and see them fail, then make the change.

- [x] 1.1 Create `backend/tests/test_accounts_password_reset.py` with this content. Verify: `uv run pytest backend/tests/test_accounts_password_reset.py -q` reports 2 failed, 1 passed. The one that passes is `test_weak_password_keeps_its_own_reason`; it guards behaviour that must not change.

  ```python
  """Password reset redemption over HTTP."""

  from typing import Any
  from uuid import uuid4

  import pytest
  from django.test import Client

  from accounts.models import Membership, PasswordReset, User
  from accounts.services import bootstrap_owner, create_password_reset

  pytestmark = pytest.mark.django_db

  PASSWORD = "Harbour-Copper-7628!Quilt"
  NEW_PASSWORD = "Cobalt-Window-9264!Birch"
  OWNER_PASSWORD = "Strong-password-928!Cedar"
  JSON = "application/json"
  UNCHANGED = {
      "detail": "Choose a different password.",
      "reason": "password_unchanged",
      "field_errors": {"password": ["This is your current password."]},
  }


  @pytest.fixture(autouse=True)
  def throttle_cache(settings: Any) -> None:
      # Throttle counts in the shared Redis cache would carry over between tests and runs.
      settings.CACHES = {
          "default": {
              "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
              "LOCATION": uuid4().hex,
          }
      }


  def make_owner() -> Membership:
      return bootstrap_owner(
          email="owner@example.test",
          full_name="Owner",
          password=OWNER_PASSWORD,
          workspace_name="Example",
          workspace_slug="example",
      )[2]


  def make_member(owner: Membership, email: str = "member@example.test") -> Membership:
      user = User.objects.create_user(email=email, full_name="Member", password=PASSWORD)
      return Membership.objects.create(workspace=owner.workspace, user=user)


  def post(client: Client, path: str, body: dict[str, Any]) -> Any:
      return client.post(path, body, content_type=JSON)


  def redeem(client: Client, secret: str, password: str) -> Any:
      return post(client, "/api/password-resets/redeem/", {"token": secret, "password": password})


  def login(client: Client, email: str, password: str) -> Any:
      return post(client, "/api/auth/login/", {"email": email, "password": password})


  def assert_untouched(reset: PasswordReset, user: User, password: str) -> None:
      generation = user.session_generation
      reset.refresh_from_db()
      user.refresh_from_db()
      assert reset.used_at is None and reset.revoked_at is None
      assert user.session_generation == generation
      assert user.check_password(password)


  def test_current_password_is_refused_and_the_link_stays_usable() -> None:
      owner = make_owner()
      member = make_member(owner)
      user = member.user
      session = Client()
      assert login(session, user.email, PASSWORD).status_code == 200
      reset, secret = create_password_reset(actor=owner, target=member)
      client = Client()

      response = redeem(client, secret, PASSWORD)

      assert response.status_code == 400
      assert response.json() == UNCHANGED
      assert_untouched(reset, user, PASSWORD)
      assert client.get("/api/auth/session/").status_code == 401
      assert session.get("/api/auth/session/").status_code == 200

      assert redeem(client, secret, NEW_PASSWORD).status_code == 200
      reset.refresh_from_db()
      user.refresh_from_db()
      assert reset.used_at is not None
      assert user.check_password(NEW_PASSWORD)
      assert session.get("/api/auth/session/").status_code == 401
      assert client.get("/api/auth/session/").status_code == 200


  def test_operator_issued_link_refuses_the_owner_current_password() -> None:
      owner = make_owner()
      reset, secret = create_password_reset(actor=owner, target=owner, issued_by_operator=True)
      client = Client()

      response = redeem(client, secret, OWNER_PASSWORD)

      assert response.status_code == 400
      assert response.json() == UNCHANGED
      assert_untouched(reset, owner.user, OWNER_PASSWORD)
      assert redeem(client, secret, NEW_PASSWORD).status_code == 200


  def test_weak_password_keeps_its_own_reason() -> None:
      owner = make_owner()
      member = make_member(owner)
      reset, secret = create_password_reset(actor=owner, target=member)

      response = redeem(Client(), secret, "weak")

      assert response.status_code == 400
      assert response.json()["reason"] == "password_rejected"
      assert response.json()["detail"] == "Choose a stronger password."
      assert response.json()["field_errors"]["password"]
      assert_untouched(reset, member.user, PASSWORD)
  ```

- [x] 1.2 In `backend/accounts/services.py`, add `from django.contrib.auth.hashers import check_password` directly below `from django.contrib.auth import get_user_model`. In `redeem_password_reset`, add the three lines below between the `except ValidationError` block and `reset.user.set_password(password)`. Leave the rest of the function unchanged. Verify: `uv run ruff check backend/accounts` passes.

  ```python
          # A reset exists because the password is lost or exposed, so it must replace it.
          if check_password(password, reset.user.password):
              raise TokenError("password_unchanged")
  ```

- [x] 1.3 In `backend/accounts/views.py`, in `error_response`, add the block below directly above `if reason == "password_rejected":`. Verify: the command from 1.1 reports 3 passed.

  ```python
      if reason == "password_unchanged":
          detail = "Choose a different password."
          return Response(
              {
                  "detail": detail,
                  "reason": reason,
                  "field_errors": {"password": ["This is your current password."]},
              },
              status=status.HTTP_400_BAD_REQUEST,
          )
  ```

## 2. Share the login attempt limit

- [x] 2.1 In `backend/tests/test_accounts_password_reset.py`, add `from django.conf import settings as django_settings` directly above `from django.test import Client`, and add the test below at the end of the file. Verify: the command from 1.1 reports 1 failed, 3 passed. The new test fails on the 429 assertion.

  ```python
  def test_password_attempts_on_a_reset_link_share_the_login_limit() -> None:
      limit = int(
          django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login_identity"].split("/")[0]
      )
      owner = make_owner()
      member = make_member(owner)
      reset, secret = create_password_reset(actor=owner, target=member)
      client = Client()

      for _ in range(limit):
          assert redeem(client, secret, PASSWORD).status_code == 400

      assert redeem(client, secret, NEW_PASSWORD).status_code == 429
      assert login(Client(), member.user.email, PASSWORD).status_code == 429
      assert_untouched(reset, member.user, PASSWORD)
      # The limit is per account: another account still signs in.
      assert login(Client(), owner.user.email, OWNER_PASSWORD).status_code == 200
  ```

- [x] 2.2 In `backend/accounts/services.py`, add this function directly above `redeem_password_reset`.

  ```python
  def password_reset_account_email(*, secret: str) -> str | None:
      """The email whose current password a reset link is compared with."""
      return (
          PasswordReset.objects.filter(token_digest=digest(secret))
          .values_list("user__email", flat=True)
          .first()
      )
  ```

- [x] 2.3 In `backend/accounts/throttling.py`, change the services import to `from accounts.services import invited_account_email, password_reset_account_email`, and add the class below directly above `LoginAddressThrottle`. Do not change the other classes. Verify: `uv run mypy` reports no issues.

  ```python
  class PasswordResetPasswordThrottle(LoginIdentityThrottle):
      """Shares the login limit, so a reset link adds no guesses at its account's password."""

      def get_cache_key(self, request: Request, view: APIView) -> str | None:
          payload = request.data
          secret = str(payload.get("token", "") if isinstance(payload, dict) else "")
          email = password_reset_account_email(secret=secret)
          return None if email is None else self.identity_key(email)
  ```

- [x] 2.4 In `backend/accounts/views.py`, add `PasswordResetPasswordThrottle` to the `accounts.throttling` import, between `LoginIdentityThrottle` and `TokenRedemptionThrottle`, and set `throttle_classes = [TokenRedemptionThrottle, PasswordResetPasswordThrottle]` on `PasswordResetRedeemView`. Verify: the command from 1.1 reports 4 passed.

- [x] 2.5 Run `uv run pytest backend/tests/test_accounts_api.py backend/tests/test_accounts_services.py backend/tests/test_accounts_models.py backend/tests/test_accounts_invitation_accept.py backend/tests/test_workspace_isolation_api.py -q`, `uv run ruff check . && uv run ruff format --check .`, and `task schema-check`. Verify: 233 passed, lint and format pass, and `schema-check` reports no API change. If it reports a change, stop and ask; do not run `task schema`.

## 3. Reset page test

The page code does not change. This test records what the page shows for a refusal.

- [x] 3.1 Add the test below at the end of `frontend/src/pages/token-preview-pages.test.tsx`. Do not change existing tests. Verify: `cd frontend && npx vitest run src/pages/token-preview-pages.test.tsx` reports 7 passed, and `cd frontend && npm run typecheck && npm run lint && npx prettier --check src/pages` passes.

  ```tsx
  test('the reset page shows why a password was refused and keeps the form', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/auth/csrf/'))
          return Promise.resolve(new Response(null, { status: 204 }))
        if (url.includes('/password-resets/preview/'))
          return Promise.resolve(response({ status: 'valid' }))
        if (url.includes('/password-resets/redeem/')) {
          bodies.push(JSON.parse(String(init?.body)))
          return Promise.resolve(
            bodies.length === 1
              ? response(
                  {
                    detail: 'Choose a different password.',
                    reason: 'password_unchanged',
                    field_errors: {
                      password: ['This is your current password.'],
                    },
                  },
                  400,
                )
              : response({
                  user: { id: '1', email: 'member@example.test', full_name: 'M' },
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
        <MemoryRouter initialEntries={['/reset-password/example']}>
          <Routes>
            <Route
              path="/reset-password/:token"
              element={<ResetPasswordPage />}
            />
            <Route path="/inbox" element={<p>Inbox reached</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const password = await screen.findByLabelText('New password')
    const confirm = screen.getByLabelText('Confirm password')
    const submit = screen.getByRole('button', { name: 'Save password' })
    await user.type(password, 'current-password')
    await user.type(confirm, 'current-password')
    await user.click(submit)
    expect(
      await screen.findByText('This is your current password.'),
    ).toBeVisible()
    expect(screen.getByText('Choose a different password.')).toBeVisible()
    expect(password).toHaveAccessibleDescription('This is your current password.')
    expect(password).toHaveValue('current-password')
    await user.clear(password)
    await user.type(password, 'another-password')
    await user.clear(confirm)
    await user.type(confirm, 'another-password')
    await user.click(submit)
    expect(await screen.findByText('Inbox reached')).toBeVisible()
    expect(bodies).toEqual([
      { token: 'example', password: 'current-password' },
      { token: 'example', password: 'another-password' },
    ])
    vi.unstubAllGlobals()
  })
  ```

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running. Use `task test-backend`, not a bare `uv run pytest`, for the full backend run. Record the test counts for the PR.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8142 RESCRIBO_E2E_FRONTEND_PORT=5142 task e2e` passes. Both variables are required; without them Playwright tests another checkout. Record the counts for the PR. If a token step answers 429 after repeated runs, clear the address limit in this worktree's Redis index only, then rerun:

  ```sh
  uv run python backend/manage.py shell -c "from django.core.cache import cache; cache.delete('throttle_token_redemption_127.0.0.1')"
  ```

- [x] 4.4 No dev server is left on 8142 or 5142, and `git status` shows only the files this change names.

## Workflow follow-up

- Archive this change in the PR that completes #142 (`/opsx:archive`). The archive adds one requirement to `openspec/specs/accounts/spec.md`; it must not reword existing text.
- PR body starts with `Fixes #142.` Milestone: G. Manual check findings.
- PR "Decisions to review": the new reason `password_unchanged` and its two strings; reset submissions share the login identity limit; the operator `--set-password` command is unchanged; no reset page change.
- PR Screenshots: "None. The reset page does not change."
- Not in this change: a password change screen, password history, and hiding the detail line on the reset page when a field error is shown.
