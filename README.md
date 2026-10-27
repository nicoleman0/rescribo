<p align="center">
  <img src="docs/assets/rescribo.png" alt="Rescribo wordmark banner" width="100%">
</p>

# Team conversations, carried through to shipped code

[![Checks](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-339933?logo=nodedotjs&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)

Mention Rescribo in a Slack thread. It drafts a GitHub issue with the relevant code, hands it to a coding agent or an engineer, and pings the thread when the pull request is ready for review.

## How it works

- **Capture:** Mention Rescribo in a Slack thread, use the message shortcut, or enter a request by hand. Ideas, bugs, feature asks, and customer reports all work.
- **Draft:** A language model groups related requests and drafts an agent-ready GitHub issue with repository context.
- **Build:** Hand the issue to a coding agent or an engineer.
- **Follow up:** Rescribo pings the conversation when the pull request is ready for review, and again when the fix ships.

Models draft and suggest. A member approves every write to GitHub and Slack. Bring your own model: OpenAI, Anthropic, Google, OpenRouter, or a local OpenAI-compatible server.

## Project status

Rescribo is in development and has no release yet.

- Working: Slack message capture, grouping, human-approved GitHub issues, fix confirmation, Slack follow-ups, and connecting a model provider.
- In progress for v0.1: AI-drafted issues ([#266](https://github.com/nicoleman0/rescribo/issues/266)), model-based matching ([#267](https://github.com/nicoleman0/rescribo/issues/267)), repository context ([#268](https://github.com/nicoleman0/rescribo/issues/268)), and thread capture by mention ([#269](https://github.com/nicoleman0/rescribo/issues/269)).
- After v0.1: coding-agent hand-off and pull request pings.

Open work is in [`openspec/changes/`](openspec/changes/) and the [milestones](https://github.com/nicoleman0/rescribo/milestones).

## Editions

Self-hosted Rescribo comes in two editions:

- **Open source** (AGPLv3): the full workflow.
- **Enterprise** (commercial license): organisation features such as SSO and audit logs. The boundary is being decided in [#271](https://github.com/nicoleman0/rescribo/issues/271).

## Roadmap

Future work currently planned or considered:

- **Microsoft Teams** capture alongside Slack.
- **Discord** capture alongside Slack.
- **GitLab** issues alongside GitHub.

## Links

- [Product specs](openspec/specs/)
- [Local development guide](docs/LOCAL_DEVELOPMENT.md)
- [Release checklist](docs/RELEASING.md)
- [Walkthrough of the demo](docs/WALKTHROUGH.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Workspace settings and provider setup](docs/SETTINGS.md)
- [Architecture and development conventions](docs/DEVELOPMENT.md)

## License

Copyright (C) 2026 Nicholas Coleman.

Rescribo is licensed under the [GNU Affero General Public License v3.0](LICENSE). A commercial license is available for organizations that want to embed or host Rescribo without the AGPL's source-sharing obligations. See [LICENSING.md](LICENSING.md).
