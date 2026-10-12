# Design

## Context

- The preview is in `github-issue-create.tsx`: a `p` with `whitespace-pre-wrap` holding `body`, then `draft.marker` in a mono line.
- The API returns `body` without the marker and `marker` as its own field (`ProblemIssuePreviewView`, `backend/feedback/views.py`). `exact_body` appends the marker only when the issue is sent.
- The e2e mock in `github-issues.spec.ts` does not match the API. It puts the marker inside `body` and returns no `marker` field.
- The preview sits in the problem page's side column, about 280px wide on desktop.
- The preview title is an `h4` under the `h3` "Review before publishing".
- The default body is the problem summary, a blank line, and `View in Rescribo: <url>`. A summary can hold single newlines.
- The app sets no Content-Security-Policy, so nothing but the renderer stops an image request.
- `react-markdown` 10.1.0, read from its source:
  - Without `rehype-raw`, a raw HTML node becomes a text node. `skipHtml` drops it instead.
  - `defaultUrlTransform` allows `http`, `https`, `irc`, `ircs`, `mailto`, `xmpp`, and every relative URL. Anything else becomes an empty string. It applies to `href` and `src`.
  - The `className` prop was removed. The caller wraps the output.

## Goals / Non-Goals

**Goals:**
- The member reads every character that will be sent. Nothing in the body is hidden.
- The preview makes no request to a third party.
- One renderer in `components/markdown/` that other screens can adopt later.

**Non-Goals:**
- Matching GitHub pixel for pixel, or rendering GitHub-only features (see the table below).
- Markdown in report text, fix notes, or follow-up messages.
- Syntax highlighting, a typography plugin, lazy loading the renderer.
- Backend or API changes.

## Decisions

1. **`Markdown` component in `frontend/src/components/markdown/markdown.tsx`.** Props: `children: string` and `headingOffset?: number`. It wraps `react-markdown` with `remark-gfm` and `remark-breaks`, no rehype plugins, and a fixed `components` map. No other props until a second caller needs one.

2. **Single newlines are line breaks, via `remark-breaks`.** GitHub renders a newline in an issue body as a line break. Without this, the default body's summary lines would run together in the preview and not on GitHub. Pending question 1.
   - No plugin: the preview is wrong for the most common body.
   - A hand-written plugin: about ten lines, but it re-implements `mdast-util-newline-to-break`.

3. **Raw HTML shows as literal text.** This is the `react-markdown` default with no `rehype-raw` and `skipHtml` off. GitHub would render a safe subset (`details`, `b`, `img`) and hide comments. The preview is a privacy check, so showing the source beats hiding it. Pending question 2.

4. **Links.** A `urlTransform` returns the URL when it is absolute with scheme `http`, `https`, or `mailto`, else an empty string. The `a` override renders `target="_blank" rel="noopener noreferrer"` when `href` is non-empty, else a `span` with the link text.
   - Narrower than the default: no `irc`, `ircs`, `xmpp`.
   - Relative URLs are inactive. In the preview they would resolve against Rescribo, and on GitHub against the repository.

5. **Images are not loaded.** The `img` override renders the same link as decision 4, with the alt text as its name, or the URL when alt is empty. An inactive URL renders the alt text only. GitHub proxies images; the preview would fetch them from the member's browser and leak the request. Pending question 3.

6. **Heading levels.** A body heading of depth `d` renders as `h{min(6, d + headingOffset)}`. Its size comes from `d`, so `#` still reads larger than `###`. The preview passes `headingOffset={4}` because its title is an `h4`. The default is `0`.

7. **Styling from theme tokens, in the `components` map.** Tailwind classes on each element. No `prose`, no new tokens.
   - Body text `text-sm`, `break-words`, block spacing by a `grid gap-2` wrapper.
   - Headings: `font-medium`, sizes `text-base` for depth 1 and 2, `text-sm` below.
   - Links: `text-primary underline underline-offset-4`, as elsewhere in the feature.
   - Inline code: `font-mono text-xs bg-muted rounded-control px-1`. Code block: the same in a `pre` with `overflow-x-auto p-3`.
   - Table: wrapped in a `div` with `overflow-x-auto`; cells `border border-border px-2 py-1`, header `font-medium`.
   - Block quote: `border-l-2 border-border pl-3 text-muted-foreground`.
   - Lists: `list-disc` and `list-decimal` with `pl-5`. A task list item drops the bullet.
   - Task checkbox: `remark-gfm` emits a disabled `input`. The override adds `aria-label` "Done" or "Not done" so axe finds a name.
   - Strikethrough and horizontal rule use the browser default with `border-border`.

8. **Preview layout.** The `p` holding `body` becomes `<Markdown headingOffset={4}>{body}</Markdown>`. The label, title `h4`, and marker line stay as they are. An empty body renders nothing between the title and the marker.

9. **GitHub-only features: keep the label, add one line.** Under "Exact preview": "GitHub also links @mentions and #references, and notifies anyone you mention." in `text-xs text-muted-foreground`. Pending question 4.

   | Feature | GitHub | Preview |
   | --- | --- | --- |
   | `@user` | link, and the user is notified | plain text |
   | `#12`, `org/repo#12`, commit SHAs | link | plain text |
   | `:emoji:` shortcodes | emoji | plain text |
   | Alerts (`> [!NOTE]`) | coloured callout | block quote with the tag as text |
   | Math, Mermaid, GeoJSON blocks | rendered | plain or code text |
   | Code fences with a language | highlighted | not highlighted |
   | Safe HTML (`details`, `kbd`, `img`) | rendered | literal text |
   | HTML comments | hidden | literal text |
   | Images | shown, proxied | link with alt text |
   | Relative links | resolve against the repository | inactive text |
   | Heading anchors | added | none |

   Tables, task lists, strikethrough, footnotes, and bare URL autolinks match, through `remark-gfm`.

10. **Fix the e2e mock to match the API.** It returns `body` without the marker and `marker` as a field. Otherwise the marker would show as literal text inside the rendered body and the marker line would be empty.

11. **`frontend/DESIGN.md` gains a "Markdown" section**: where the renderer lives, that it never renders HTML or loads images, and the heading offset rule. Shared file; pending question 5.

## Risks / Trade-offs

- Three dependencies and their `unified` tree add to the bundle. → The problem page is not the entry route's critical path; measure with `task build` and report the size change in the PR.
- "Exact preview" overstates the match for bodies that use GitHub-only features. → The note in decision 9 names the two with side effects.
- A member may expect an image to show. → The link carries the alt text and opens the image on request.

## Open Questions

Numbered as in the plan summary: 1 `remark-breaks`, 2 raw HTML as text or dropped, 3 images, 4 the GitHub-only note, 5 the `DESIGN.md` section. The artifacts assume the recommended answer for each.
