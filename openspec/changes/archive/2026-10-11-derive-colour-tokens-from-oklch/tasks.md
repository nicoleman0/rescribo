# Tasks

Delivers #197. Refactor; `skip_specs: true`. Frontend only. Change only the files named below. Do not rename a token, touch the `@theme` block, or edit anything below the dark block in `theme.css`. Do not add sidebar tokens (#198) or palettes (#203).

Ports for this worktree: api 8197, web 5197. See `.claude/brief.md` before starting servers.

Write the check first (group 1) and see it pass on today's CSS. Then change the tokens (group 2).

## 1. The tolerance check

- [x] 1.1 Create `frontend/e2e/theme-tokens.spec.ts`:

  ```ts
  import { expect, test } from '@playwright/test'

  // Each token's colour before the palette variables existed (#197): [light, dark].
  const REFERENCE: Record<string, [string, string]> = {
    '--background': ['#fbfbfc', '#0f0f14'],
    '--sidebar': ['#f4f4f7', '#131319'],
    '--card': ['#ffffff', '#17171f'],
    '--raised': ['#ffffff', '#1c1c25'],
    '--raised-muted': ['#f4f4f7', '#24242e'],
    '--card-foreground': ['#16161d', '#ececf1'],
    '--border': ['#e4e4ea', '#26262f'],
    '--foreground': ['#16161d', '#ececf1'],
    '--muted-foreground': ['#62626e', '#a0a0ae'],
    '--muted': ['#f4f4f7', '#1d1d26'],
    '--secondary': ['#f4f4f7', '#1d1d26'],
    '--secondary-foreground': ['#16161d', '#ececf1'],
    '--accent': ['#f4f4f7', '#1d1d26'],
    '--accent-foreground': ['#16161d', '#ececf1'],
    '--input': ['#e4e4ea', '#34343f'],
    '--selected': ['#ececf3', '#23233a'],
    '--primary': ['#5b5bd6', '#8b8cf5'],
    '--primary-foreground': ['#ffffff', '#101018'],
    '--destructive': ['#b42318', '#ffa399'],
    '--destructive-foreground': ['#ffffff', '#101018'],
    '--ring': ['#5b5bd6', '#8b8cf5'],
    '--tone-neutral': ['#f0f0f4', '#24242d'],
    '--tone-neutral-foreground': ['#4b4b57', '#b8b8c5'],
    '--tone-neutral-dot': ['#9a9aa6', '#7a7a88'],
    '--tone-info': ['#ebebfd', '#24244a'],
    '--tone-info-foreground': ['#3f3fb0', '#b2b2ff'],
    '--tone-info-dot': ['#5b5bd6', '#8b8cf5'],
    '--tone-progress': ['#e6f0fb', '#142a42'],
    '--tone-progress-foreground': ['#1d5ca3', '#92c2f5'],
    '--tone-progress-dot': ['#3b82d6', '#5aa2ec'],
    '--tone-success': ['#e3f3ea', '#12301f'],
    '--tone-success-foreground': ['#17613f', '#84d8a8'],
    '--tone-success-dot': ['#2f9e64', '#3fbf7a'],
    '--tone-warning': ['#fbeedb', '#3a2a11'],
    '--tone-warning-foreground': ['#8a4b00', '#f2bd66'],
    '--tone-warning-dot': ['#d98a1c', '#e6a23c'],
    '--tone-danger': ['#fde8e6', '#3f1915'],
    '--tone-danger-foreground': ['#b42318', '#ffa399'],
    '--tone-danger-dot': ['#e0483a', '#f0675a'],
  }

  // Fixed tokens must match exactly. Derived tokens may round by one step per channel.
  const FIXED = /^--(tone-|destructive$)/

  const channels = (hex: string) =>
    [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16))

  for (const [index, theme] of (['light', 'dark'] as const).entries()) {
    test(`${theme} colour tokens match their original values`, async ({
      page,
    }) => {
      await page.emulateMedia({ colorScheme: theme })
      await page.goto('/sign-in')
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)

      // getComputedStyle returns oklch() text, so paint each colour and read the sRGB pixel.
      const painted = await page.evaluate((tokens) => {
        const probe = document.createElement('div')
        document.body.append(probe)
        const canvas = document.createElement('canvas')
        canvas.width = canvas.height = 1
        const context = canvas.getContext('2d', { willReadFrequently: true })!
        const result: Record<string, number[]> = {}
        for (const token of tokens) {
          probe.style.backgroundColor = `var(${token})`
          context.clearRect(0, 0, 1, 1)
          context.fillStyle = getComputedStyle(probe).backgroundColor
          context.fillRect(0, 0, 1, 1)
          result[token] = [...context.getImageData(0, 0, 1, 1).data]
        }
        probe.remove()
        return result
      }, Object.keys(REFERENCE))

      const wrong = Object.entries(REFERENCE).flatMap(([token, hexes]) => {
        const want = channels(hexes[index])
        const [red, green, blue, alpha] = painted[token]
        const error = Math.max(
          ...[red, green, blue].map((value, i) => Math.abs(value - want[i])),
        )
        const allowed = FIXED.test(token) ? 0 : 1
        return alpha === 255 && error <= allowed
          ? []
          : [`${token}: wanted ${hexes[index]}, painted ${painted[token]}`]
      })
      expect(wrong).toEqual([])
    })
  }
  ```

  The `alpha === 255` test also catches a token that does not resolve: the probe is then transparent.
- [x] 1.2 Run it on the unchanged CSS, from `frontend`: `RESCRIBO_E2E_API_PORT=8197 RESCRIBO_E2E_FRONTEND_PORT=5197 npx playwright test e2e/theme-tokens.spec.ts`. Verify both tests pass. This proves the table equals `main`.
- [x] 1.3 Prove the check can fail: change `--border` in `:root` to `#e4e4ec`, run 1.2 again, and verify the light test fails naming `--border`. Revert the edit.

## 2. Derive the tokens

- [x] 2.1 `frontend/src/styles/theme.css`, `:root` block. Replace the lines from `--background` through `--ring` with the block below. `color-scheme: light;` stays directly above it. The `--shadow-hairline` line is unchanged.

  ```css
    /* Palette: the surface, border, text, and brand tokens derive from these. */
    --brand-hue: 278;
    --brand-chroma: 0.184;
    --neutral-tint: 0.004;

    --background: oklch(0.986 var(--neutral-tint) var(--brand-hue));
    --sidebar: oklch(0.968 var(--neutral-tint) var(--brand-hue));
    --card: oklch(1 0 0);
    --raised: oklch(1 0 0);
    --raised-muted: oklch(0.968 var(--neutral-tint) var(--brand-hue));
    --shadow-hairline: 0 1px 1px rgb(0 0 0 / 0.03);
    --card-foreground: oklch(0.204 calc(var(--neutral-tint) * 3) var(--brand-hue));
    --border: oklch(0.921 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --foreground: oklch(0.204 calc(var(--neutral-tint) * 3) var(--brand-hue));
    --muted-foreground: oklch(0.501 calc(var(--neutral-tint) * 4) var(--brand-hue));
    --muted: oklch(0.968 var(--neutral-tint) var(--brand-hue));
    --secondary: oklch(0.968 var(--neutral-tint) var(--brand-hue));
    --secondary-foreground: oklch(0.204 calc(var(--neutral-tint) * 3) var(--brand-hue));
    --accent: oklch(0.968 var(--neutral-tint) var(--brand-hue));
    --accent-foreground: oklch(0.204 calc(var(--neutral-tint) * 3) var(--brand-hue));
    --input: oklch(0.921 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --selected: oklch(0.945 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --primary: oklch(0.541 var(--brand-chroma) var(--brand-hue));
    --primary-foreground: oklch(1 0 0);
    --destructive: #b42318;
    --destructive-foreground: oklch(1 0 0);
    --ring: oklch(0.541 var(--brand-chroma) var(--brand-hue));
  ```

- [x] 2.2 Same block. Change the tone comment to `/* Status tones: background, text, and dot. Fixed: they do not follow the palette. */`. Leave the 18 `--tone-*` values and the three `--elevation-*` values as they are.
- [x] 2.3 Same file, `:root[data-theme='dark']` block. Replace the lines from `--background` through `--ring` with the block below. `color-scheme: dark;` stays directly above it.

  ```css
    --brand-hue: 281;
    --brand-chroma: 0.152;
    --neutral-tint: 0.008;

    --background: oklch(0.172 var(--neutral-tint) var(--brand-hue));
    --sidebar: oklch(0.192 var(--neutral-tint) var(--brand-hue));
    --card: oklch(0.209 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --raised: oklch(0.231 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --raised-muted: oklch(0.266 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --shadow-hairline: 0 1px 1px rgb(0 0 0 / 0.5);
    --card-foreground: oklch(0.943 var(--neutral-tint) var(--brand-hue));
    --border: oklch(0.273 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --foreground: oklch(0.943 var(--neutral-tint) var(--brand-hue));
    --muted-foreground: oklch(0.713 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --muted: oklch(0.235 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --secondary: oklch(0.235 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --secondary-foreground: oklch(0.943 var(--neutral-tint) var(--brand-hue));
    --accent: oklch(0.235 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --accent-foreground: oklch(0.943 var(--neutral-tint) var(--brand-hue));
    --input: oklch(0.331 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --selected: oklch(0.268 calc(var(--neutral-tint) * 5) var(--brand-hue));
    --primary: oklch(0.685 var(--brand-chroma) var(--brand-hue));
    --primary-foreground: oklch(0.177 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --destructive: #ffa399;
    --destructive-foreground: oklch(0.177 calc(var(--neutral-tint) * 2) var(--brand-hue));
    --ring: oklch(0.685 var(--brand-chroma) var(--brand-hue));
  ```

  Leave the dark `--tone-*` and `--elevation-*` values as they are. Change the comment above the block to `/* Each theme is one block that sets the palette variables and redefines every colour token. */`.
- [x] 2.4 If the formatter wraps the long lines, keep its output. Verify: `git diff main -- frontend/src/styles/theme.css` shows changes only inside the two theme blocks, no token name added or removed apart from the three palette variables, and no `--tone-*` or `--elevation-*` value changed.

## 3. Prove the tolerance

- [x] 3.1 Run 1.2 again. Verify both tests pass. If a token fails, stop and ask. Do not change a lightness, a multiplier, or the tolerance yourself.
- [x] 3.2 Prove the built CSS too. From `frontend`: `npm run build`, then start `API_PROXY_TARGET=http://127.0.0.1:8197 npx vite preview --host 127.0.0.1 --port 5197 --strictPort`, then run `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5197 npx playwright test e2e/theme-tokens.spec.ts`. Verify both tests pass. Stop the preview server. If a test fails for a reason other than a colour, stop and ask.
- [x] 3.3 Record for the PR: per theme, how many tokens match exactly and how many are 1/255 off. Planning measured, among the 20 derived tokens, 11 exact and 9 off by one in light, and 10 exact and 10 off by one in dark. All 19 fixed tokens were exact.

## 4. Unit test

- [x] 4.1 `frontend/src/lib/theme.test.ts`, test `every theme block defines every colour token the light theme does`: change the value filter to `/#|rgb|oklch|var\(--border\)/`. Without `oklch` the test counts fewer than 30 colour tokens and fails.
- [x] 4.2 Same file. Add a test `every theme block sets the palette variables`: the `:root` block and each other theme's block define `--brand-hue`, `--brand-chroma`, and `--neutral-tint`. A block that omits one would silently inherit the light value. Lift the `block` helper out of the existing test so both tests share it.
- [x] 4.3 Same file. Add a test `status tones and destructive are fixed values`: in every theme block, each `--tone-*` token and `--destructive` has a value matching `/^#[0-9a-f]{6}$/`. Verify it fails when `--tone-info-dot` is set to `var(--primary)`, then revert.
- [x] 4.4 From `frontend`: `npm test`. Verify 0 failed.

## 5. Docs

- [x] 5.1 `frontend/DESIGN.md`: add this section between `## Themes` and `## Status tones`. Do not reword existing text.

  ```md
  ## Palette

  Each theme block sets three palette variables: `--brand-hue`, `--brand-chroma`,
  and `--neutral-tint`. The surface, border, text, and brand tokens are `oklch()`
  values built from them. Each token keeps its own lightness, and a neutral
  token takes a whole-number multiple of the tint. Status tones and
  `--destructive` are fixed hex values and do not follow the palette.
  `e2e/theme-tokens.spec.ts` pins the default palette to its original colours.
  ```

## 6. Screenshots

- [x] 6.1 The before shots are in `.claude/shots/before` (42 files). Take the after shots into `.claude/shots/after` and build `.claude/shots/compare.html` as the brief describes.

## 7. Repository checks

- [x] 7.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 7.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. `schema-check` must report no API change.
- [x] 7.3 `RESCRIBO_E2E_API_PORT=8197 RESCRIBO_E2E_FRONTEND_PORT=5197 task e2e` passes. Record the counts for the PR. If an axe contrast check or `dark raised surfaces keep contrast` in `motion.spec.ts` fails, stop and ask. Do not adjust a colour to pass it.
- [x] 7.4 No server is left on 8197 or 5197. `task worker-check` is not needed: no worker wiring changes.

## Workflow follow-up

- Archive this change in the PR that completes #197 (`/opsx:archive`).
- PR milestone: H. Product-grade UI.
- PR "Decisions to review": palette variables are set per theme; neutrals take whole-number multiples of the tint; neutrals share the brand hue; `--destructive` stays fixed; the token check stays in the repo.
- PR Checks: give the exact and off-by-one counts from 3.3, for the dev server and the built CSS.
