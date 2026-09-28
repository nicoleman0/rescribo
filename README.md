<p align="center">
  <img src="docs/assets/rescribo.png" alt="Rescribo wordmark banner" width="100%">
</p>

# Customer feedback, carried through to a fix

[![Checks](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-339933?logo=nodedotjs&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)

Rescribo is being built to help teams turn customer reports into engineering work and keep track of the follow-up that comes after a fix.

## The workflow

- **Capture:** Record a customer report. Manual entry is available; Slack capture has a separate implementation path.
- **Connect:** Group related reports, link a GitHub issue, or review and approve a new issue before publication.
- **Follow up:** Review fixes and track customer outcomes. This workflow is planned.

## Project status

Rescribo is an early development scaffold. Workspace accounts, invitations, the report inbox, problem grouping, and the GitHub issue workflow are implemented. Live GitHub provider behaviour for the product path remains to be verified with a disposable repository. Fix confirmation and customer follow-up are planned.

## Links

- [MVP specification](docs/MVP_SPEC.md)
- [Local development guide](docs/LOCAL_DEVELOPMENT.md)
- [Workspace settings and provider setup](docs/SETTINGS.md)
- [Architecture and development conventions](docs/DEVELOPMENT.md)
- [Implementation milestone](https://github.com/nicoleman0/rescribo/milestone/1)

## License

Copyright (C) 2026 Nicholas Coleman.

Rescribo is licensed under the [GNU Affero General Public License v3.0](LICENSE). A commercial license is available for organizations that want to embed or host Rescribo without the AGPL's source-sharing obligations — see [LICENSING.md](LICENSING.md).
