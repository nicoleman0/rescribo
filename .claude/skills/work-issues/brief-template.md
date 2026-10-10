# Brief: issue #{issue}

You work on one issue in your own git worktree. A coordinator session reviews your plan and your PR and relays questions to the maintainer. Answers to your questions arrive as files in `.claude/answers/`.

- Issue: #{issue}, {title}. Read it with `gh issue view {issue} --comments`.
- Worktree: `{path}`, branch `{branch}`.
- Ports: API {api}, frontend {web}. Database `{database}`, Redis index {redis_index}.
- You own: {owned_paths}. Anything else is shared: ask before you change it.
- Milestone for the PR: {milestone}.

## Issue notes from the coordinator

{notes}

## Isolation (required)

Postgres and Redis run in Docker from the main checkout and are already up. Your `.env` already points at your own database and Redis index. They listen on the host ports in `RESCRIBO_DATABASE_URL` and `RESCRIBO_REDIS_URL`, not the defaults 5432 and 6379. Check those before reporting them down.
- Never run `task services`, `task stop`, or `docker compose`. Never touch ports 8000 or 5173, the main checkout, or another worktree.
- Dev servers: `RESCRIBO_SLACK_FAKE_DELIVERY=true uv run python backend/manage.py runserver 127.0.0.1:{api} --noreload`, and from `frontend`, `API_PROXY_TARGET=http://127.0.0.1:{api} npm run dev -- --host 127.0.0.1 --port {web} --strictPort`. Stop them when you finish.
- Checks: `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check`, and `RESCRIBO_E2E_API_PORT={api} RESCRIBO_E2E_FRONTEND_PORT={web} task e2e`. Without those two variables Playwright reuses another checkout's server and tests the wrong code. Run `task worker-check` too if you change worker wiring.

## Screenshots (UI changes only)

Seed the demo with `RESCRIBO_DEMO_PASSWORD='Rescribo-demo-e2e-2026!' uv run python backend/manage.py seed_demo`. Then, from the worktree root, run `SHOTS_BASE=http://127.0.0.1:{web} node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/<before|after>`. The planner takes the before shots and the implementer takes the after shots. `.claude/shots/` is git-ignored, and both sessions can read it. Build the comparison page with `.claude/skills/work-issues/scripts/compare.py` into `.claude/shots/compare.html`; its usage is in the file header.

## Shared files

`frontend/DESIGN.md` and the `openspec/specs/` files may change in parallel branches. Add your own section or requirement and never reword existing text, so merges stay trivial.

## PR

Use plain, short sentences. The sections are Changes, Decisions to review, Checks (with real numbers), and Screenshots. Leave Screenshots as "Pending": the coordinator fills it in. Follow the maintainer's rules: no Claude or AI attribution anywhere, no em-dashes, and code comments that say why rather than what.
