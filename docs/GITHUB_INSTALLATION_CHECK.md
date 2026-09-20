# GitHub App installation feasibility check

This opt-in check covers GitHub issue #1. It uses a disposable GitHub App and repository. It does not create a production connection or persist credentials.

## Test app settings

Create a private GitHub App with:

- one callback URL that points to a local or temporary HTTPS callback you control;
- repository permission **Issues: Read and write**;
- the implicit **Metadata: Read-only** permission;
- no other repository, organisation, or account permissions;
- installation limited to one disposable repository.

GitHub recommends selecting the minimum permissions required by the app. The [permission guide](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app) maps issue creation to Issues write access.

Generate a private key. Keep the key, client secret, authorisation code, user token, and installation token outside the repository. The result file contains only repository identity, visibility, permission names, connection state, and token expiry.

## Run the check

Set these values in the shell or the ignored `.env.github-feasibility` file:

```sh
export RESCRIBO_GITHUB_APP_ID=...
export RESCRIBO_GITHUB_CLIENT_ID=...
export RESCRIBO_GITHUB_CLIENT_SECRET=...
export RESCRIBO_GITHUB_PRIVATE_KEY_PATH=/absolute/path/to/test-app.pem
export RESCRIBO_GITHUB_REDIRECT_URI=http://127.0.0.1:8765/callback
```

For a local live check, start the callback listener and a ten-minute, single-use authorisation session. Use a synthetic workspace identifier and bind the expected disposable repository into the state:

```sh
task github-installation-check -- run \
  --workspace feasibility-a \
  --repository owner/disposable-repository
```

Open the printed URL within three minutes. The loopback callback listener receives the short-lived code and state without printing either value, completes the check, and returns a safe message to the browser.

The separate start and complete commands remain available when a callback listener is not suitable:

```sh
task github-installation-check -- start --workspace feasibility-a --repository owner/repository
task github-installation-check -- complete --workspace feasibility-a --state ... --code ...
```

The check consumes state before exchanging the code. It derives the installation from the repository instead of trusting a callback installation ID, verifies the authorised user can access it, requires exactly one selected repository, and creates a short-lived installation token restricted to that repository. It then reads the repository identity and visibility. Tokens are neither printed nor written to disk. These checks follow GitHub's documentation for [user access tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app), [installation repositories](https://docs.github.com/en/rest/apps/installations), and [restricted installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).

The sanitised result is written to `.cache/github-installation-result.json`. Review it before using it as evidence. Live results and app settings belong in the Milestone A evidence PR for issue #8, separate from mocked test results.

To test access loss, suspend or uninstall the disposable app and rerun the completion step with a new authorisation session. The result must report `suspended` or `revoked_or_unavailable` rather than `active`.
