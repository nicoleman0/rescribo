# ADR 0009: Versioned production images on GHCR

Status: accepted. Issue [#252](https://github.com/nicoleman0/rescribo/issues/252).

Production services use exact-version images from GHCR. A release tag publishes
the backend and proxy for amd64 and arm64. Release candidates get their own
version tag; only final releases move `latest`. `compose.prod.yaml` keeps its
build definitions so source builds remain available. Compose pulls the named
image first and builds from source when that image cannot be pulled.

The version in `pyproject.toml` is the release source of truth. A workflow gate
requires the tag and both compose image tags to match it before publishing.
