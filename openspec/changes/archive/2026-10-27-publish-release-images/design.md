# Design

## Context

- `backend/Dockerfile` has a `production` target. It compiles the Rust matcher
  in a `rust:1.92-slim-trixie` stage. `proxy/Dockerfile` builds the frontend in
  a `node:24-slim` stage and copies `dist` into `caddy:2.11-alpine`. The
  frontend has no build-time environment, and the Caddyfile reads
  `RESCRIBO_SITE_ADDRESS` at runtime, so both images are host-agnostic.
- `task prod-up` runs `docker compose build` first, so today it always builds.
- The repository is public, so GitHub's native arm64 runners are free.
- `[project] version` in `pyproject.toml` is the version's source of truth
  (#254).
- The first release candidate uses `0.1.0rc1` in `pyproject.toml` and
  `0.1.0-rc.1` in both compose image tags. #254 owns the version bump; the
  coordinator aligns its release checklist before the tag is pushed.
- The maintainer's `surgite` repo already publishes to GHCR with
  `docker/metadata-action` and `docker/build-push-action`. This follows the
  same pattern.

## Goals / Non-Goals

**Goals:**

- A pushed version tag publishes both images, multi-platform, with no stored
  secret beyond `GITHUB_TOKEN`.
- A self-hoster pulls images instead of building.

**Non-Goals:**

- Creating GitHub Releases or release notes (#254).
- Signing, SBOMs, or build attestations beyond buildx defaults.
- Rewriting the self-hoster docs (#253).
- Pinning PostgreSQL, Redis, or Caddy by digest (ADR 0007 open item).

## Decisions

### Image names

`ghcr.io/nicoleman0/rescribo-backend` and `ghcr.io/nicoleman0/rescribo-proxy`.
They keep today's local names and are flat, so each is its own package.
Alternative: nested `ghcr.io/nicoleman0/rescribo/backend`. GHCR supports it,
but it gains nothing and reads less like the current tags.

### Tags

`docker/metadata-action` with `type=semver,pattern={{version}}` and the
default `latest=auto` flavour. A final tag `v0.1.0` gives `0.1.0` and
`latest`. A prerelease tag `v0.1.0-rc.1` gives only `0.1.0-rc.1`:
metadata-action never adds `latest` to a semver prerelease. No `0.1` moving
tag: before 1.0 a minor release may break, and `compose.prod.yaml` pins the
exact version anyway. The metadata step also writes the OCI labels, and
`org.opencontainers.image.source` links each package to the repository.

### Trigger and version gate

`on: push: tags: ['v*']`. A first job checks, and fails the run before any
build when one does not hold:

1. The tag is `vX.Y.Z` or `vX.Y.Z-rc.N`.
2. The tag without `v` equals `pyproject.toml`'s version, compared as PEP 440
   versions (`packaging.version.Version`), so `0.1.0-rc.1` matches
   `0.1.0rc1`, the spelling uv and Python tools write.
3. Both `image:` tags in `compose.prod.yaml` equal the tag without `v`
   (exact string).

The check runs inline in the workflow with `uv run --no-project --with
packaging`. Alternative: `on: release: published`, as in `surgite`. A tag push
lets a release candidate publish without a GitHub Release.

Pull requests that touch the release workflow or either Dockerfile build both
images on the host platform without pushing. The version gate and release
matrix run only for tag pushes.

### Platforms and runners

`linux/amd64` and `linux/arm64`. A matrix builds each image on a native
runner (`ubuntu-24.04` and `ubuntu-24.04-arm`), pushes by digest, and a merge
job creates the multi-platform manifest with `docker buildx imagetools
create`. This is Docker's documented pattern for native multi-platform
builds. Alternative: one job with QEMU. Less YAML, but the Rust release build
and `uv sync` run emulated, which likely takes tens of minutes per release.
The GitHub Actions cache (`type=gha`) is scoped per image and platform.

### How the frontend reaches the proxy image

Unchanged: `proxy/Dockerfile` builds it in its `frontend` stage. The release
workflow builds that Dockerfile as is. No separate frontend artifact.

### `compose.prod.yaml`

Each `image:` names the GHCR image with the exact version, for example
`ghcr.io/nicoleman0/rescribo-backend:0.1.0`. A self-hoster takes
`compose.prod.yaml` from the release tag, so the file and the images it names
always match, and the RC clean install exercises the file the final release
ships. The `build:` sections stay. Per the Compose build specification, when a
service has both `image` and `build` and no `pull_policy`, Compose pulls the
image first and builds only when the pull fails. So:

- A host without the source pulls.
- Someone building from source runs `docker compose -f compose.prod.yaml
  build` (or `task prod-build`), which tags the local build with the same name.
  `up` then finds the image locally and does not pull.

Alternative: `${RESCRIBO_VERSION}` from `.env.production`. One knob for
upgrades and no second copy of the version, but a host can then run images
with a compose file from another release, and `.env.production.example`
belongs to #257.

### `task prod-up`

Its first step, `docker compose build`, must go, or it builds from source and
shadows the published image. Compose pulls missing images on `run` and `up`.
A new `prod-build` task covers source builds. `Taskfile.yml` is outside this
change's owned paths, so this needs the coordinator's approval.

## Risks / Trade-offs

- [The workflow cannot run before a real tag] → Build both images locally with
  the workflow's arguments and check `docker compose -f compose.prod.yaml
  config`. The PR lists what only a tag proves: GHCR login and push,
  native arm64 runners, the manifest merge, tag selection, package linking.
- [New GHCR packages are private] → The maintainer sets both public once after
  the first push. The PR says so.
- [Version lives in two files] → The release gate fails on any mismatch, so a
  drift cannot publish. #254's bump procedure updates both.
- [Compose pull-then-build fallback] → If a pull fails on a host without
  source, the build fallback fails too, loudly, because the Dockerfiles are
  missing. Only a real RC install proves the pull path end to end.
- [Overwriting a published tag] → GHCR allows it. A bad release is fixed with a
  new version, not by re-pushing the same tag.

## Migration Plan

1. Merge. Nothing publishes until a tag.
2. Maintainer sets pyproject and compose to `0.1.0rc1` / `0.1.0-rc.1`, tags
   `v0.1.0-rc.1`, makes both packages public, and runs the clean install.
3. Rollback: delete the tag and the package versions. No running system
   depends on them yet.
