# Proposal

## Why

Delivers #75. When the capture shortcut runs on a message that already has a report, the "Already captured" notice and report link are shown before the linked-member check. Any user in the connected Slack team learns that the message was captured and gets the report ID. The `slack-capture` spec says an unlinked user gets link instructions only.

## What Changes

- Check for a linked active membership before looking up an existing report.
- An unlinked user gets the same link-code capture modal whether or not the message is already captured. Showing a different modal would still reveal capture status.
- After the user links with a code on submission, idempotent capture returns the existing report and its link, as it does today for linked members.
- Linked members still see "Already captured" with the link straight away.

## Capabilities

### New Capabilities

### Modified Capabilities
- `slack-capture`: an unlinked user learns nothing about existing reports, including whether the message is captured

## Impact

`start_capture` in `backend/connections/slack_inbound.py` and its tests in `backend/tests/test_slack_capture.py`. No API, schema, or migration changes.
