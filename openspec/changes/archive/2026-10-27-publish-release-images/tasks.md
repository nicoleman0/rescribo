# Tasks

## 1. Release workflow

- [x] 1.1 Add `.github/workflows/release.yml` for `push: tags: ['v*']` and pull requests touching the workflow or either Dockerfile. Release jobs use only `contents: read` and `packages: write`; the PR job builds both images without pushing. Do not add cancel-in-progress. Verify: `actionlint` (or `npx yaml-lint` if actionlint is missing) passes on the file.
- [x] 1.2 Add the version gate job from design.md: tag format, PEP 440 match with `pyproject.toml`, exact match with both `compose.prod.yaml` image tags. Verify with a matching RC fixture (`pyproject.toml` version `0.1.0rc1`, compose tags `0.1.0-rc.1`) that `v0.1.0-rc.1` passes; verify it fails against the current `pyproject.toml` version, and that `v0.1.0` and `v0.1` fail against the RC compose tags. Paste the outputs in the PR.
- [x] 1.3 Add the build matrix (image x native runner) that pushes by digest, with `docker/metadata-action` labels and per-image, per-platform `type=gha` cache. Verify: build both images locally for the host platform with the same Dockerfile, target, and context the matrix passes (`docker buildx build -f backend/Dockerfile --target production .` and `docker buildx build -f proxy/Dockerfile .`), and record build times.
- [x] 1.4 Add the merge job that creates each multi-platform manifest with `docker buildx imagetools create`, tagged by metadata-action (`{{version}}`, `latest=auto`). Verify: run `docker/metadata-action`'s tag rules mentally against `v0.1.0` and `v0.1.0-rc.1` and state in the PR which tags each gets; the real proof is the RC tag.
- [x] 1.5 Cross-build both images for the platform opposite the host (`--platform linux/arm64` on amd64, or `--platform linux/amd64` on arm64). Verify: both builds succeed.

## 2. Compose and docs

- [x] 2.1 In `compose.prod.yaml`, set `image: ghcr.io/nicoleman0/rescribo-backend:0.1.0-rc.1` and `image: ghcr.io/nicoleman0/rescribo-proxy:0.1.0-rc.1`, keeping the `build:` sections. Verify: `docker compose -f compose.prod.yaml --env-file <scratch env with POSTGRES_PASSWORD and RESCRIBO_DOMAIN> config` shows both GHCR references and the worker and scheduler inherit the backend image.
- [x] 2.2 Drop the `build` step from `prod-up` and add `prod-build`. Verify: `task --list` shows both and `task --dry prod-up` no longer runs `build`.
- [x] 2.3 Update only the image-related lines in `docs/DEPLOYMENT.md`: the service table's Image column, the "Images build from source" line, the build step wording, and the Update row. Verify: `git diff docs/DEPLOYMENT.md` touches no other section.

## 3. Checks

- [x] 3.1 Run `npx @fission-ai/openspec validate --all --strict`.
- [x] 3.2 Run `task check test build schema-check` with PostgreSQL and Redis running, and record the counts in the PR.

## Workflow follow-up

- Archive the change in the PR that completes it.
- The PR lists what only a real tag proves and the one-time step of making both GHCR packages public.
