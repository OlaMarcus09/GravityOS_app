# Existing-user trial invitation delivery readiness — November 3, 2026

## Current gate

The existing-user claim feature remains live. The invitation delivery work is in PR #7 and is **not deployed**. No test or customer invitation has been sent. Production still runs commit `2955850e79b830fba44875726f10e5d629e7fe12`. The claim deadline remains November 15, 2026 at 23:59:59 WAT. Flutterwave LIVE checkout remains disabled.

The Render `RESEND_API_KEY` returned HTTP 401 for read-only domain, suppression, and metrics requests. That does not establish whether the key can send, whether `gravityos.tech` is verified, or whether the test inbox is suppressed. Public SPF/DKIM DNS records exist, but Resend's verification status is unavailable. **Do not send the authorized test email until an account-scoped audit credential can read `/domains`, `/domains/{id}`, `/suppressions`, and `/usage`, and all checks pass.** Keep the sending credential server-side. Do not paste either key into GitHub, chat, logs, or build artifacts.

Local checks: the full API suite passed after the final provider/quota guard refinement (233 tests, one dependency deprecation warning). Frontend typecheck and production build passed with the existing local environment and network access for Google Fonts. The opt-out browser test passed on desktop, mobile, and tablet using installed Chrome. A full repository-wide Ruff run found two pre-existing unused imports in `routers/projects.py` and `schemas/releases.py`; focused lint on the changed invitation code passed. The new SQL has not yet been rehearsed on PostgreSQL 17, so this is not a production release approval.

PR #7 CI run `41581673184` passed on implementation commit `bd25c0901e2f3711a631a0e1092ff39c1aeb2558`. An aggregate-only HTTPS read of production eligibility on November 3 found 22 Free owner candidates: 12 eligible, eight needing email confirmation, one already claimed, and one otherwise ineligible. All 12 eligible owners currently permit general email notifications. This still does **not** establish the final recipient count because Resend suppressions, dedicated promotional opt-outs, and email deduplication have not been verified against a deployed ledger.

## Prepared controls

- Migration `0033_trial_invitation_delivery.sql` adds private, RLS-enabled delivery and promotional opt-out tables. Unique campaign/kind/owner and campaign/kind/email-digest indexes prevent duplicate reservations. It has not been applied.
- The unsubscribe URL uses a signed opaque delivery ID in a fragment. Opening the link shows a confirmation page; a deliberate POST records the preference through a service-only RPC. The API key used to sign links must be a new server-only `TRIAL_INVITATION_SIGNING_KEY` of at least 32 random characters. The link and endpoint do not claim a trial.
- The test sender accepts only `highmarcus.eth@gmail.com`, stores a separate `test` ledger row with no user or workspace ID, and has no customer-send CLI. `TRIAL_INVITATION_SENDING_ENABLED` defaults to false. It must remain false on Render.
- The sender rechecks domain, SPF, DKIM, account usage, all provider suppressions, local opt-outs, and current claim eligibility before sending. A failed or partial provider read blocks the send. An attempted send is committed to the ledger before the external call; unknown outcomes never trigger an automatic retry. Provider API acceptance is recorded as `accepted`, not `delivered`; a later read of Resend's last event is needed to record delivery, bounce, or complaint.
- The invitation template includes a first-name greeting with neutral fallback, an early-user thank-you, the exact claim deadline, no-card/no-charge/data-retention copy, an authenticated Settings CTA, and the opt-out link in HTML and text.

## Remaining release sequence

1. Founder or Resend account administrator verifies `gravityos.tech` sending status and each SPF/DKIM record in the Resend dashboard, confirms quota, and provisions a separate account-scoped audit key in a private operator environment. A sending-only key cannot satisfy the read gates.
2. Review the migration and complete an isolated PostgreSQL 17 restore rehearsal. Confirm the new private tables and service-only function are inaccessible to `anon` and `authenticated`, and verify the opt-out and unique-claim behavior with test rows. Do not apply migration 0027 or alter trial campaign settings.
3. Add the signing key to Render through its secret manager and deploy migration 0033, API, and frontend only after reviewed PR CI, backup, and rollback checks pass. Keep invitation sending disabled. Browser-test the public opt-out page and authenticated CTA; test the API with an inserted disposable test-ledger row.
4. Recheck production eligibility read-only and account suppressions immediately before any test send. The last aggregate checkpoint was 12 potentially eligible Free owners; the final count is unverified until the current opt-outs and Resend suppressions can be read. Keep recipient addresses out of outputs.
5. Run a synthetic render first. With all gates green, run the single founder-authorized test command with the audit key, sending key, signing key, and production PostgreSQL DSN in a private operator environment. The operator must set `TRIAL_INVITATION_SENDING_ENABLED=true` only for that invocation. The command refuses a second reservation for the test inbox and never retries automatically. Reconcile the Resend message ID to a delivery event and inspect the inbox and authentication headers before reporting delivery.
6. Stop before any customer batch. A separate founder approval is required. A batch action is deliberately absent from this PR while provider verification and the test remain blocked.

Synthetic dry run:

```sh
PYTHONPATH=apps/api python apps/api/scripts/send_trial_test_invitation.py
```

Single authorized test, **only after every gate above passes**:

```sh
TRIAL_INVITATION_SENDING_ENABLED=true PYTHONPATH=apps/api python apps/api/scripts/send_trial_test_invitation.py --send-authorized-test
```

Required private environment variables for the latter: `GRAVITYOS_TRIAL_INVITE_DSN`, `RESEND_AUDIT_API_KEY`, `RESEND_API_KEY`, `TRIAL_INVITATION_SIGNING_KEY`, and `EMAIL_FROM=Gravity OS <notifications@gravityos.tech>`. Do not run that command from CI or a shared shell history containing literal secret values.
