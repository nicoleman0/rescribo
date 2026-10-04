## 1. Capture order

- [x] 1.1 In `start_capture`, look up the linked membership before the existing report, and show "Already captured" only to a linked member
- [x] 1.2 Test that an unlinked actor on a captured message gets the link-code capture modal with no report link or ID
- [x] 1.3 Test that the same actor submitting a valid code gets "Already captured" with the existing report link, and the report count stays at one
- [x] 1.4 Test that a revoked membership on a captured message is treated as unlinked

## 2. Checks

- [x] 2.1 Run `npx @fission-ai/openspec validate --all --strict`
- [x] 2.2 Run `task check test build schema-check`
