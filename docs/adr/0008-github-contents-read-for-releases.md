# ADR 0008: Contents read for GitHub releases

Status: accepted. 8 October 2026.

The GitHub App requests **Contents: Read-only** so members can list and link releases from the selected repository. GitHub requires Contents read for the [release listing and lookup endpoints](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps).

The app continues to request only Issues write and Metadata read by default. Only release operations request a token with Contents read. Installations that have not accepted the additional permission remain usable for issue operations, while release listing and linking explain that the installation owner must grant access.
