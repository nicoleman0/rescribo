# Proposal

Delivers GitHub issue [#252](https://github.com/nicoleman0/rescribo/issues/252).

## Why

Self-hosters must build the production images themselves. `compose.prod.yaml`
uses local tags (`rescribo-backend:prod`, `rescribo-proxy:prod`) and no
workflow publishes images, so a deployment needs Docker build tooling and the
full source tree. The first release (milestone I) needs images a host can pull.

## What Changes

- A release workflow runs when a version tag is pushed (`v0.1.0`,
  `v0.1.0-rc.1`). It fails unless the tag matches `[project] version` in
  `pyproject.toml` and the image tags in `compose.prod.yaml`.
- Pull requests that change the release workflow or either Dockerfile build
  both images without pushing.
- It builds the backend (`production` target) and proxy images for
  `linux/amd64` and `linux/arm64` and pushes them to
  `ghcr.io/nicoleman0/rescribo-backend` and `ghcr.io/nicoleman0/rescribo-proxy`.
- Every release gets its exact version tag. Only a final release moves
  `latest`. A release candidate never does.
- `compose.prod.yaml` references both images by exact version. The `build:`
  sections stay, so building from source keeps working.
- `docs/DEPLOYMENT.md`: only the image-related lines change. #253 rewrites the
  self-hoster docs.

No product behaviour changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- New `.github/workflows/release.yml`.
- `compose.prod.yaml` image references.
- `docs/DEPLOYMENT.md` service table and update row.
- GHCR gets two new packages under the `nicoleman0` account. They start
  private and must be made public once by the maintainer.
- Version bumps (#254) must update the compose image tags with the version.
