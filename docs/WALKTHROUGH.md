# Walkthrough

A ten-minute tour of the seeded demo workspace. Every name and message in it is
fictitious, and nothing reaches Slack or GitHub. To run it locally:

```sh
task demo-seed   # prints the visitor sign-in
```

Then sign in at the app origin. The visitor is a member, so owner-only actions
are refused. The demo resets to this state every night at 03:00 UTC, or when you
run `task demo-seed` again.

Labels below were checked against the app on 2026-10-07.

## 1. Inbox: capture

Every screen shows a **Demo** badge and "Fictitious data. Nothing is sent to
Slack or GitHub."

- The inbox lists 16 reports from Slack and manual entry. Filter by status,
  assignee, or source.
- Open **Search ignores accented names**. Under **Source**, the Slack message is
  a snapshot taken at capture time, not a live copy.
- **Triage** offers **Link to problem**, **Create problem**, and **Dismiss**.
  Choose **Create problem**, then **Create and link**. The report is now
  **Linked**.
- **Dark mode please** was dismissed by mistake; it duplicates Northwind's
  request. Use **Restore report**, then link it to **Add dark mode to the
  customer portal**.

## 2. Problems: connect

A problem groups reports about the same underlying cause.

- **CSV export times out…** has three reports. **Download button greyed out…**
  was first linked to the invoice problem by mistake, then moved here.
- Its GitHub issue #412 is linked, not copied. GitHub owns the engineering work.
- **Calendar sync creates duplicate events** shows an issue creation that GitHub
  never confirmed. Rescribo does not retry blindly: **Check creation result**
  looks for the issue, and **Stop recovery and unblock this problem** needs a
  note saying what you checked.
- **Mobile app signs users out…** links issue #455, which shows **Access issue**:
  it moved somewhere the connection cannot read.
- **Add dark mode…** is **Not planned**, with the reason recorded.
- **Create GitHub issue** on any problem is refused here: "Integrations are
  disabled in the demo workspace." With a real connection, it shows a preview
  you approve before anything is published.

## 3. Follow-ups: close the loop

**Password reset emails arrive after the link expires** has a confirmed fix
(4.13), so each of its six reports gets a follow-up for the employee who took it.

- **Completed**: the employee was notified and recorded the customer outcome:
  **Confirmed**, **No response**, or **Still affected**.
- **Delivery problem**: one message **Failed** and one is **Uncertain**: Slack may
  or may not have received it. An uncertain send is never resent automatically;
  a member checks Slack first.
- **Needs approval**: **Password reset loop** is a draft addressed to you, the
  visitor. Edit the message, then **Send to Slack**. In the demo the send is
  simulated and labelled **Sent (simulated)**. Then record the customer outcome.

Employee messages and customer contact are tracked separately. Rescribo never
contacts customers itself.

## 4. Settings

**Settings** shows the Slack and GitHub connections, with counts of queued,
failed, and uncertain operations, and a note that integrations are disabled.
Invitations, member changes, and workspace deletion are owner actions, and the
visitor cannot use them.

## Not shown by the demo

- Live Slack capture through the message shortcut, real GitHub issue creation,
  and the OAuth setup for both. Earlier live checks are in
  [LIVE_INTEGRATION_EVIDENCE.md](LIVE_INTEGRATION_EVIDENCE.md). The full journey
  will be recorded by the [manual end-to-end check](MANUAL_CHECK.md).
- Match suggestions. They stay off because the matcher failed its precision gate
  ([MATCHING_EVALUATION.md](MATCHING_EVALUATION.md)).

## Architecture and decisions

- [DEVELOPMENT.md](DEVELOPMENT.md): modules, runtime flow, and boundaries.
- [ADRs](adr/): accounts and sessions (0001), feedback domain (0002), local Rust
  matcher (0003), notification cancellation (0004), platform and integrations
  (0005), marketing site (0006), single-host deployment (0007).
- [DEPLOYMENT.md](DEPLOYMENT.md): running it yourself.
