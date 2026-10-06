# UAT pilot

Track the pilot in [issue #57](https://github.com/nicoleman0/rescribo/issues/57).
Start after #13 merges. Record the tested commit and each journey's
Pass / Fail / Blocked / Not run result there. Create one issue per finding,
label it `uat` plus `bug` or `enhancement`, and link it to the tracker.
File findings with the "UAT finding" issue form.

## Starting from scratch

The pilot starts with an empty product database, migrations applied, and no demo
or E2E seed data. The operator creates the first owner interactively. The owner
then invites members and connects GitHub and Slack through Settings.
There is no public signup. See [accounts setup](LOCAL_DEVELOPMENT.md) and
[provider operator setup](SETTINGS.md).

A database reset removes local users, workspaces, reports, connections, and
history. It does not uninstall Slack/GitHub Apps or delete upstream issues/messages.
Use a disposable GitHub repository and Slack workspace for the pilot. Use fresh
provider apps/installations if the upstream registration journey is also under test.
Keep existing operator credentials and the encryption key in private configuration.

## Reset procedure, to run when the pilot is ready

Do not run this during #13 implementation or while another test/process is writing
to the target database. This procedure is for the main checkout's Compose-backed
development database. An isolated worktree or external database needs its own
verified target; do not assume these commands apply.

1. Pull the merged #13 build and complete its automated checks before resetting.
2. Inspect Compose PostgreSQL mounts, configured database identity, and all
   API/worker/scheduler consumers. Verify that the target is the disposable pilot
   database and identify any other databases in that PostgreSQL instance.
   Do not print `.env` or a resolved Compose configuration containing secrets.
3. Stop the target API, frontend, worker, scheduler, and E2E processes. For the
   container app, `docker compose --profile app stop backend frontend worker scheduler`
   leaves PostgreSQL/Redis running. Stop only the relevant host processes too.
4. If data is worth keeping, create a private backup before deletion:

```sh
umask 077
mkdir -p .cache/uat
docker compose exec -T postgres sh -eu -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > .cache/uat/before-reset.sql
```

5. Recreate only the verified configured database. These commands use the
   PostgreSQL container's database/user settings and delete that database's data:

```sh
docker compose exec -T postgres sh -eu -c 'dropdb --force -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T postgres sh -eu -c 'createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

6. Prevent old queued tasks from reaching the fresh database. Prefer a verified
   unused Redis database index and a pilot-specific Celery queue. Point the API,
   worker, scheduler, Django cache, and worker check at the same pilot Redis URL
   and `RESCRIBO_CELERY_DEFAULT_QUEUE`. Verify the selected index is unused by
   other worktrees. Do not use `FLUSHALL` or delete shared Redis volumes.
   If the intended Redis DB is confirmed exclusive to this pilot, clearing that
   DB while all its consumers are stopped is an alternative. Record the choice.
7. Verify `RESCRIBO_DATABASE_URL` targets the recreated database, including any
   inherited environment overrides. Apply migrations using the same runtime as
   the pilot. For host development, run `task migrate`. For the container app:

```sh
docker compose --profile app run --rm backend uv run --no-sync python backend/manage.py migrate
```

8. Before creating the owner, verify zero product users, workspaces, reports,
   problems, connections, follow-ups, and external operations through a read-only
   ORM check in that runtime. Record counts, not sensitive row contents.
9. Bootstrap your real pilot owner interactively. Replace the example values:

```sh
task bootstrap-owner -- --email owner@example.test --full-name 'Pilot Owner' --workspace-name 'UAT Pilot' --workspace-slug uat-pilot
```

For the container app, use the equivalent management command in `backend` with
an interactive terminal. Enter the password at the prompt. Do not put it in
arguments, tracker comments, or committed configuration. Do not use `e2e-test`
as the workspace slug and do not run a seed command.

10. Start the API, frontend, worker, and scheduler with consistent pilot settings.
    Confirm `RESCRIBO_SLACK_FAKE_DELIVERY=False`, readiness, and a real worker
    round trip. Do not run `task e2e` against the pilot during manual testing;
    it creates synthetic accounts and may use fake delivery.
11. Open a fresh browser profile so old cookies and session-stored report drafts
    do not carry over. Record the commit, app origin, and environment in #57.

Do not remove whole PostgreSQL volumes or use `docker compose down --volumes`:
the cluster or Redis volume may contain another worktree's data.

## Live connections

- Set up operator keys privately as described in [SETTINGS.md](SETTINGS.md).
  An empty product database does not replace this operator configuration.
- Use a stable HTTPS origin reachable by Slack and GitHub. The application public
  base URL, allowed hosts, CSRF trusted origins, browser proxy, and registered
  callbacks/webhooks must agree. The ordinary local Vite server restricts hosts;
  configure the chosen tunnel/proxy rather than assuming its default host works.
- Bootstrap determines the workspace ID. Register its actual callback URLs before
  testing authorisation. Never attach callback query strings or OAuth codes.
- In Settings, connect GitHub, select the disposable repository, and confirm
  publication consent. Connect Slack, approve channels, and link the employee
  identity. Invite a second member in a separate browser profile.
- Follow #57's journeys through capture, grouping, issue preview/publish, closure,
  fix confirmation, employee DM, and independent customer contact/outcome.
- Record actual provider observations separately from local or mocked evidence.
  Use fictitious customer feedback and redact private identifiers as needed.

## Triage and exit

Blockers prevent continuation or involve data loss/access failure. Major bugs
break a core workflow. Minor findings have a workaround or affect presentation.
Feature requests describe the unmet task and example, then receive a fix/defer
decision. Link already planned work instead of creating duplicates.

Fix and retest blockers and major workflow bugs before pilot acceptance. Record
decisions for remaining findings and acceptance in #57, then proceed to milestone
C and D. UAT does not replace their automated failure/isolation checks or matching
evaluation.
