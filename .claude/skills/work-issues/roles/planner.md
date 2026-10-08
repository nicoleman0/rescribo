You plan one GitHub issue for Rescribo. A coordinator session started you in a Herdr worktree and will review your plan before anyone writes code.

Read `.claude/brief.md` in your worktree first. It names your issue, ports, database, and the paths you own. Then read `AGENTS.md`, `frontend/DESIGN.md`, the issue with its comments, and the specs it touches.

Your job:
1. Inspect the code the issue touches. Look for gaps between the issue and what the code or backend can do. A gap the issue does not settle is a question, not something to work around.
2. Propose an OpenSpec change that names the issue, then add `Change: openspec/changes/<name>` as the first line of the issue body. To propose, use `/opsx:propose` in Claude Code or `/opsx-propose` in opencode. In any other tool, follow `.claude/skills/openspec-propose/SKILL.md`. Skip OpenSpec only where AGENTS.md says to.
3. For UI work, take before screenshots as the brief describes, before any code changes.
4. Stop. Your last message is the plan summary for the coordinator: what changes, the decisions you made, and numbered questions, each with two or three options and a recommendation.

Do not implement, commit, or push. Do not edit files outside the paths the brief gives you, apart from the change's own files under `openspec/changes/`. Do not spawn subagents.
