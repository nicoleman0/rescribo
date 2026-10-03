# ADR 0005: Platform and integration choices

Status: accepted. Moved from the former MVP specification. Sources checked 20 September 2026; live results are in [LIVE_INTEGRATION_EVIDENCE.md](../LIVE_INTEGRATION_EVIDENCE.md).

## Platform

- Confirmed: internal team inbox, Slack first, GitHub for engineering tracking, Python backend, React + TypeScript frontend.
- Django + DRF over FastAPI, because the product has substantial account, permission, data-editing, and migration work. React owns the interface; no separate Node backend. [T3, T4]
- Celery with Redis and one Beat scheduler, using established retry machinery instead of a custom queue. Business operation state stays in PostgreSQL. [T5]
- Start with a container deployment on infrastructure the developer controls. Managed cloud is a later learning milestone. Hosting provider is still open.

## Slack

| Option | Finding | Decision |
| --- | --- | --- |
| Message shortcut | Keeps the selected message and can open a modal; needs `commands`; acknowledge within three seconds. [S1, S2] | Use **Submit customer feedback** on a message. |
| Slash command / global shortcut | Does not supply the selected message. [S1] | Manual entry in the web app covers this. |
| Events API message intake | Would mean continuous collection and filtering. | Subscribe to lifecycle events only. |
| Thread retrieval | Needs history scopes; distribution-dependent rate limits. [S3] | Capture one message plus submitter context. |
| `response_url` | Five responses within 30 minutes. [S4] | Immediate acknowledgement only, never follow-up. |
| Bot DM | `conversations.open` then `chat.postMessage`. [S5, S6] | Send approved follow-ups to the submitting employee. |

Develop in a test workspace, then use unlisted distribution for a limited pilot. Commercial distribution may still need Marketplace review. [S10]

## GitHub

| Option | Finding | Decision |
| --- | --- | --- |
| GitHub App | Selected repositories and separate issue permissions. [G1] | Use installation credentials, not a personal token. |
| Issues API | Installation tokens create and read issues with Issues write/read. [G2] | Request Issues read/write and Metadata read only. |
| Webhooks | Signed deliveries, delivery IDs, prompt acknowledgement, missed-delivery recovery. [G3] | Persist receipts, process asynchronously, reconcile linked issues. |

Installation lifecycle events arrive without a subscription; only Issues needs one. GitHub will not deselect the last repository, so access loss may arrive as installation deletion. Both repository removal and installation deletion were observed live as HTTP 404. [G6]

## Sources

- [S1](https://docs.slack.dev/interactivity/implementing-shortcuts/), [S2](https://docs.slack.dev/reference/interaction-payloads/shortcuts-interaction-payload/), [S3](https://docs.slack.dev/reference/methods/conversations.replies/), [S4](https://docs.slack.dev/interactivity/handling-user-interaction/), [S5](https://docs.slack.dev/reference/methods/conversations.open/), [S6](https://docs.slack.dev/reference/methods/chat.postMessage/), [S7](https://docs.slack.dev/reference/methods/conversations.info/), [S8](https://docs.slack.dev/authentication/verifying-requests-from-slack/), [S9](https://docs.slack.dev/reference/methods/chat.getPermalink/), [S10](https://docs.slack.dev/app-management/distribution/), [S11](https://docs.slack.dev/authentication/installing-with-oauth/), [S12](https://docs.slack.dev/reference/events/app_uninstalled/)
- [G1](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app), [G2](https://docs.github.com/en/rest/issues/issues), [G3](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks), [G4](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-with-a-github-app-on-behalf-of-a-user), [G5](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation), [G6](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
- [T1 Vite](https://vite.dev/guide/), [T2 TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview), [T3 Django auth](https://docs.djangoproject.com/en/5.2/topics/auth/default/), [T4 DRF auth](https://www.django-rest-framework.org/api-guide/authentication/), [T5 Celery with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html)
