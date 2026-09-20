# GitHub issue lifecycle feasibility check

This opt-in check covers GitHub issue #2. It uses the disposable GitHub App and repository from the [installation check](GITHUB_INSTALLATION_CHECK.md). It does not create a production connection, persist credentials, or write raw webhook payloads to disk.

## Test app settings

Start from the installation check app settings, then add webhook delivery:

- **Webhook URL:** a disposable [smee.io](https://smee.io) channel. Start a new channel per run; do not reuse channels across checks.
- **Webhook secret:** a random value. It stays in the ignored `.env.github-feasibility` file.
- **Subscribe to events:** *Issues*, *Installation*, and *Installation repositories*. The *Meta* event is not required.
- Permissions remain **Issues: Read and write** and the implicit **Metadata: Read-only**.

Keep the private key, client secret, user token, installation token, and webhook secret outside the repository. The result file contains only the repository identity, issue number, event actions, delivery identifiers, connection states, and timestamps.

## Run the check

Set these values in the shell or the ignored `.env.github-feasibility` file (the first five match the installation check):

```sh
export RESCRIBO_GITHUB_APP_ID=...
export RESCRIBO_GITHUB_CLIENT_ID=...
export RESCRIBO_GITHUB_CLIENT_SECRET=...
export RESCRIBO_GITHUB_PRIVATE_KEY_PATH=/absolute/path/to/test-app.pem
export RESCRIBO_GITHUB_REDIRECT_URI=http://127.0.0.1:8765/callback
export RESCRIBO_GITHUB_WEBHOOK_SECRET=...
```

Run the check with a synthetic workspace identifier:

```sh
task github-lifecycle-check -- \
  --workspace feasibility-a \
  --repository owner/disposable-repository \
  --smee-url https://smee.io/your-disposable-channel
```

Optional rejection probes:

- `--pull-request-url` checks that linking a pull request from the disposable repository is rejected. The app cannot create pull requests (it lacks Contents permission), so open one manually in the disposable repository first.
- `--other-issue-url` checks that linking an issue from another repository is rejected before any API request.

What the check does, in order:

1. Repeats the installation verification and mints a repository-restricted installation token.
2. Creates a disposable issue and reads it back.
3. Resolves the issue's own URL, and runs the optional pull request and cross-repository rejection probes.
4. Starts a loopback receiver for webhooks. When prompted, forward the smee channel to it from another terminal:

   ```sh
   npx --yes smee --url https://smee.io/your-disposable-channel \
     --target http://127.0.0.1:8765/webhooks
   ```

   The port comes from `RESCRIBO_GITHUB_REDIRECT_URI`. The check then closes and reopens the issue through the API. Every delivery's `X-Hub-Signature-256` is verified on arrival; bad signatures are rejected with HTTP 401. Each verified event is applied by fetching current issue state from the API and comparing provider `updated_at` values, so a stale delivery cannot overwrite newer state. The webhook payload itself is never trusted for state.
5. Removes the repository from the installation, expects an `installation_repositories` removal event, and confirms the issue is inaccessible (access-lost, not closed).
6. Deletes the installation, expects an `installation` deletion event, and confirms installation token creation fails (access-lost).

The user token from step 1 is held in memory only and used for the repository removal call; it is never stored. This mirrors the product rule to discard setup credentials after verification.

The sanitised result is written to `.cache/github-issue-lifecycle-result.json`, including the ordered delivery log (delivery IDs, event names, actions, and receive times only). Review it before using it as evidence. Live results and app settings belong in the Milestone A evidence PR for issue #8, separate from mocked test results. Raw payloads are processed in memory to verify signatures and extract state, and are never written to disk.

## Expected observations to record

- Whether closing an issue through the REST API without a `state_reason` produces `completed`, `null`, or another value in the fetched state and webhook payload.
- The exact delivery ordering of `issues`, `installation_repositories`, and `installation` events, including any duplicates or retries.
- Which HTTP status GitHub returns for issue reads and token creation after repository removal and installation deletion.
