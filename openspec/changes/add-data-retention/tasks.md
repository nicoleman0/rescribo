# Tasks

## 1. Receipt retention

- [ ] 1.1 Add a periodic task that clears payloads of successful receipts older than seven days
- [ ] 1.2 Test that deduplication still works after the purge and that failed receipts keep their payload

## 2. Backup and restore

- [ ] 2.1 Document backup schedule, retention, and the deletion caveat
- [ ] 2.2 Add a restore smoke test as a script and Task target
- [ ] 2.3 Run it and record the result

## 3. Checks

- [ ] 3.1 Run `task check test build schema-check` and `task worker-check`
