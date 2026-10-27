# Releasing

How to cut a Rescribo release. `[project] version` in `pyproject.toml` is the one source of truth for the version; the release workflow fails when the tag, `pyproject.toml`, and the image tags in `compose.prod.yaml` disagree.

## Checklist

1. On a release branch, set `[project] version` in `pyproject.toml` to the PEP 440 form (`0.1.0rc1` for the candidate) and both image tags in `compose.prod.yaml` to the tag form (`0.1.0-rc.1`).
2. Move the `## [Unreleased]` entries in `CHANGELOG.md` into a new version section and update the compare links.
3. Merge, then push the tag `vX.Y.Z-rc.N` from `main`. The image workflow runs on `v*` tags and publishes the candidate images.
4. Clean-install check: follow the self-hoster quickstart with the candidate images, sign in, open the user menu, and confirm it shows the candidate version.
5. For the final release, set `pyproject.toml` to `X.Y.Z`, both image tags in `compose.prod.yaml` to `X.Y.Z`, and the date in the changelog heading. Merge, then push `vX.Y.Z`.
6. Publish the GitHub release with the notes template below.

After the first published release, make both GHCR packages public once.

## Release notes template

```
<One-line summary of the release.>

## Highlights

<Short list copied from the changelog section.>

## Upgrade

<Notes for existing hosts, or a link to the upgrade steps once #253 lands
in docs/DEPLOYMENT.md.>

## Images

`ghcr.io/nicoleman0/rescribo-backend:X.Y.Z`
`ghcr.io/nicoleman0/rescribo-proxy:X.Y.Z`

## Full changelog

See [CHANGELOG.md](https://github.com/nicoleman0/rescribo/blob/main/CHANGELOG.md).
```

Deployment of both images runs from `compose.prod.yaml` behind Caddy; see `docs/DEPLOYMENT.md`.
