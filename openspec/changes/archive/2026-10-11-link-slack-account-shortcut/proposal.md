# Proposal

## Why

A member can only reach the Slack linking code prompt by running "Submit customer feedback" on some message. They have no feedback to submit at that point, so the step makes no sense. Delivers #149 with option 2 of the issue: a dedicated entry point in Slack.

## What Changes

- Add a global shortcut, "Link Rescribo account". It opens a modal with one field, the linking code from Settings.
- Submitting the modal redeems the code for the signed Slack actor and team, through the same rule the capture modal uses.
- A member who is already linked sees a notice instead of the code field.
- Settings and the "Account not linked" notice name the new shortcut.
- The capture modal keeps its linking field for an unlinked member (open question 2 in `design.md`).
- No new scope. No slash command. No Sign in with Slack.

## Capabilities

### New Capabilities

### Modified Capabilities
- `slack-connection`: "Slack account linking" gains the dedicated shortcut. One new requirement covers what the shortcut shows.

## Impact

- Backend: `backend/integrations/slack/shortcuts.py`, `modals.py`, `backend/connections/slack_inbound.py`, and the payload routing in `SlackInteractionsView.post` (`backend/connections/views.py`, the `try` block that dispatches on `payload["type"]`). No model change and no migration.
- Frontend: one sentence in `frontend/src/features/settings/slack-account.tsx`.
- Docs: `docs/slack-app-manifest.json` gains the shortcut. `docs/PROVIDER_SETUP.md` gains the step to update an existing Slack app.
- Live Slack app: the maintainer updates the manifest and runs the live check listed in `design.md`.
- API schema: unchanged. The interactions endpoint is excluded from OpenAPI.
