# ADR 0001: Account tokens and sessions

Status: accepted

## Decisions

- Account secrets are 256-bit CSPRNG tokens. Store a SHA-256 digest for indexed lookup, then compare the presented secret with `hmac.compare_digest`. Passwords remain Django-hashed and validated.
- Workspace permissions resolve active membership on every scoped request. A missing membership returns 404; an authenticated non-owner receives 403.
- A `session_generation` value invalidates all browser sessions after global revocation. Session rows remain in PostgreSQL so Redis cache eviction does not sign users out.
- At least one active owner is maintained by a transactional service check. Direct ORM writers can violate this invariant; tests cover application use cases.
- Owner role changes are last-write-wins until row versions are added.

An active-sessions screen can later use Django session rows or a session-key index. Neither is needed until the product exposes session management.
