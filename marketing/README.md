# Marketing site

The public site builds independently from `frontend/`. It has no authentication,
API calls, or product bundle. README owns the headline and workflow copy;
`openspec/config.yaml` supplies the product context. Copy describes the intended
shipped workflow in present tense. It does not report development progress.

Use Node 24 from the repository's `.node-version`:

```sh
cd marketing
npm ci
npm run dev
```

Build and verify:

```sh
npm run check
npm run build
npx playwright install chromium
npm test
npm run check:links
npm run preview
```

GSAP ScrollTrigger connects native scrolling to the 3D pose and workflow
transitions. The motion control remains reachable throughout the page and
pauses both ambient and scroll-driven animation. Reduced motion keeps the
scene and content static. Scrolling and links work without JavaScript.

The build writes portable static files to `dist/`. Asset URLs are relative, so
the site can be hosted at a domain root or under a directory. Three.js enhances
the static illustration. Reduced motion, the pause button, offscreen suspension,
and context-loss fallback are checked against the built site.

## Canonical URL

The site directs visitors to the self-hosted project repository. It has no
application sign-in link. `MARKETING_SITE_URL` adds canonical metadata when
supplied. It must be an absolute HTTPS URL without credentials and is a public
build value. It is not required to build or publish the public site.

```sh
MARKETING_SITE_URL=https://YOUR-MARKETING-DOMAIN/ npm run build
```

Build probes use a synthetic canonical URL to verify rendering and validation.
`npm run check:links` checks generated assets,
fragments, and HTTPS URL structure. After real URLs are chosen, check external
destinations with:

```sh
npm run check:links -- --live
```

## Deployment

Hosting and domain selection are pending under issue #53. There is no deploy
workflow or DNS change. Before publishing, choose a static host and domain,
build with the canonical URL, check live destinations, and upload `dist/` as
one artifact. Verify the deployed page, asset loads, and navigation. Keep the
prior build for rollback; restore that artifact without changing the product
deployment.
