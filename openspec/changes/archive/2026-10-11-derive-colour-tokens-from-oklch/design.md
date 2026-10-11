# Design

## What the fit found

Today's values were converted to OKLCH and fitted in Chromium, the only browser the e2e suite runs. The tolerance is 1/255 per channel.

| Idea | Result |
| --- | --- |
| One brand hue and chroma for both themes | Fails. `--primary` is 6/255 off in both themes. Light needs hue 277.5 to 279, dark needs 280 to 282. |
| One flat neutral chroma per theme | Fails. Light `--background` and `--muted-foreground` are 3/255 off and `--sidebar` 2/255. Dark `--foreground` is 3/255 off and `--muted-foreground` 2/255. (Estimated from the conversion maths.) |
| One tint per theme, each token a whole-number multiple | Passes. Worst error 1/255. |
| Neutrals at the brand hue, not their own hue (about 285.5 today) | Passes. The neutrals carry too little chroma for the hue shift to show. |

Today's neutrals are greys with a blue offset that grows toward the mid-tones, so their chroma varies with lightness. That is why one flat chroma cannot reproduce them.

## Decisions

- **Palette variables are set per theme block.** Light: hue 278, chroma 0.184, tint 0.004. Dark: hue 281, chroma 0.152, tint 0.008. A palette is six numbers.
- **Neutral tokens use `calc(var(--neutral-tint) * n)`.** `n` is 1 to 5 and belongs to the token, like its lightness. Light uses 1, 2, 3, 4. Dark uses 1, 2, 5.
- **Neutrals share `--brand-hue`.** No separate neutral hue variable.
- **Pure white is `oklch(1 0 0)`.** A tint at lightness 1 is out of gamut and would clip unevenly.
- **`--destructive` stays a fixed hex value.** It is a danger colour and equals `--tone-danger-foreground` in both themes. `--destructive-foreground` is white or a dark neutral, so it derives.
- **`--ring` repeats the `--primary` expression.** No token aliases another. The existing test expects every theme block to define every colour token, and aliasing is a separate refactor.
- **Shadows and elevation stay as they are.** They are alpha values, not surface, border, text, or brand colours.
- **The fixed tokens stay hex.** They do not need a new notation, and hex keeps them exact.

## The tolerance check

`frontend/e2e/theme-tokens.spec.ts` holds a table of every colour token's hex value on `main` at `5133271`. For each theme it paints each token's computed colour on a 1x1 canvas and reads the 8-bit sRGB pixel. `getComputedStyle` alone is not enough: it returns `oklch(...)` text for the new values.

The canvas reading was compared with painted screenshot pixels for all 39 tokens in both themes while planning. They agreed.

The test stays in the repo. It pins the default palette while #198, #202, and #203 edit the same file.

## Risks

- 19 of the 40 derived values sit 1/255 from today's colour. A contrast pair that passes by a hair could fail. The axe checks in `themes.spec.ts`, `motion.spec.ts`, and the other e2e specs cover this. If one fails, stop and ask. Do not adjust a colour to pass it.
- The fit ran against values injected into the dev server page, not through the Tailwind build. Tasks 3.1 and 3.2 run the check through both pipelines.
- `motion.spec.ts` compares two `getComputedStyle` strings for `--raised` and `--card`. Both sides become `oklch(...)` text, so the comparison should still hold.
