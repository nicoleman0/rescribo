# ADR 0006: Separate static marketing site

Status: accepted. Issue [#53](https://github.com/nicoleman0/rescribo/issues/53).

The public site lives in `marketing/` with its own Vite/TypeScript build,
lockfile, and CI checks. HTML owns content and navigation; Three.js is an
optional visual enhancement. It does not load the React application or call
the product API.

This keeps marketing content and deployment independent of product releases.
A route in the product app would couple those releases and load the app's
runtime. A hosted builder would move content outside the repository.

The site presents Rescribo as self-hosted and links to the project repository.
It has no authentication or application sign-in link. Hosting and domain
selection are deferred until deployment readiness; the build produces portable
static files.
