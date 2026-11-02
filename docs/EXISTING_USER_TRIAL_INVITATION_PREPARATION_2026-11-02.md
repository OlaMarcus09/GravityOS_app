# Existing-user trial invitation preparation — November 2, 2026

## Release and recipient state

PR #6 merged as `2955850e79b830fba44875726f10e5d629e7fe12`. Migration 0032 is applied and the existing-user claim window began at 2026-11-02 12:29:45.126235 UTC. It closes at **2026-11-15 22:59:59 UTC (23:59:59 WAT)**. The original new-user campaign remains unchanged. A disposable pre-campaign owner claimed once at 12:30:20.589193 UTC; its expiry is exactly 604800 seconds later. No customer claim was made by the release operator.

An aggregate-only production query after that disposable claim found **12 eligible Free owners** among owned Free workspaces. It also found two already-claimed owners, eight owners requiring email confirmation, and one other ineligible Free-workspace owner. These counts are a snapshot, not a send list. They do not yet account for Resend suppressions or a promotion-specific opt-out. The final recipient count is therefore **unverified**.

## Existing provider and preview

The application already has a Resend HTTP client and an email outbox for product notifications (`apps/api/app/integrations/resend.py`, `apps/api/app/jobs/notifications.py`, migration 0021). Render has a nonempty `RESEND_API_KEY`, sender `Gravity OS <notifications@gravityos.tech>`, reply-to `notifications@gravityos.tech`, and `WEB_APP_URL=https://www.gravityos.tech`. These are configuration observations, not proof of successful delivery or domain verification. A read-only `GET /domains` request returned 401; the key may be restricted or invalid, so Resend account access must verify the sender domain, key permissions, and suppression list before sending.

`apps/api/app/integrations/trial_invitation.py` renders individual HTML and text messages. The synthetic preview command is:

```sh
PYTHONPATH=apps/api python apps/api/scripts/preview_trial_invitation.py --first-name Alex --output /private/tmp/gravityos-trial-invitation-preview.html
```

The subject is **Your 7 Days of GravityOS Pro Are Waiting 🎁**. The message greets the person by first name, falls back to “Hi there,”, gives the exact WAT deadline, and says the full 168 hours start only after the owner presses **Claim My Trial**. It says no card, no automatic charges, and existing data retained. The CTA is the authenticated `https://www.gravityos.tech/settings` page; opening it does not claim. The preview uses a deliberately fake unsubscribe URL and **must never be sent**.

## Private selection and required send controls

`apps/api/app/jobs/trial_invitation_candidates.py` selects one owned Free/`none` workspace per owner, calls the production `private.existing_user_trial_status` function for the live claim policy, applies the general `email_enabled` preference, normalizes the confirmed Auth email, uses the profile display name, deduplicates by SHA-256 email digest, and excludes verified Resend suppressions. It only returns recipients in process memory. Without a current suppression snapshot, it withholds every recipient and reports aggregate pending counts. `apps/api/scripts/preview_trial_recipients.py` is an operator-only, aggregate-output preview; it requires a production PostgreSQL DSN in `GRAVITYOS_TRIAL_INVITE_DSN`, never logs the DSN, and accepts only a mode-0600 JSON suppression snapshot marked `source=resend` and verified within the preceding hour. It has no send action. A live selector dry run on November 2 encountered a DNS resolution failure, so the last verified production count remains the earlier aggregate of 12; no identities were logged.

The eventual sender must run as a private operator job, never a public API. At the start of each batch and immediately before each individual send, use a read-only database snapshot to select confirmed `auth.users` joined to a chosen owned Free/`none` workspace and `profiles.display_name`. Require `private.existing_user_trial_status(owner_id, workspace_id, clock_timestamp()) = 'eligible'`. Select one workspace per owner, and normalize the confirmed Auth email. Exclude `notification_preferences.email_enabled=false`, any dedicated promotional opt-out, and every address on the current Resend account suppression list. Recheck the claim ledger and paid/manual conflict at dispatch so eligibility changes after preview cannot result in a send. Never output raw addresses in terminal, GitHub, CI, Render logs, or repository artifacts; keep any recipient manifest in an ignored, mode-0600 private recovery directory and delete it after the run.

The current notification preference model controls all email, but has **no promotion-specific preference**, one-click trial-invitation unsubscribe route, or local suppression mirror. The existing outbox worker renders only its generic notification template and does not recheck trial eligibility at delivery. Do not enqueue invitations there yet. Before any customer batch:

1. Add a promotion-specific opt-out and a signed, single-purpose unsubscribe endpoint, with an RLS-safe preference record. The link must work without signing in and must not expose email or identity in the URL or logs. Honor the opt-out both during selection and immediately before dispatch.
2. Read Resend account suppressions with a credential permitted to list them, and fail closed if that read fails. Include bounce and complaint suppression webhooks or a safe reconciliation step.
3. Add a private invitation delivery ledger, with one unique `(owner_id, invite_kind)` key for the initial invite and a distinct key for at most one optional reminder. Store attempt state, provider message ID, timestamps, and sanitized error codes. Do not put raw email in public logs. Preserve ledger entries across retries.
4. Use `ResendClient.send_email` with a stable idempotency key derived from the ledger row. Claim rows atomically before sending. On timeout, reconcile with Resend before retrying; never issue a different idempotency key for the same invite.
5. Recheck eligibility and preferences for the reminder, send it only to still eligible unclaimed owners, and send no more than once. Stop all sends at the claim deadline.
6. Provide a preview-only dry run and a separate explicit batch action. The batch action must require the founder's later approval and must fail if the campaign, suppression, opt-out, sender verification, or provider checks are not current.

No batch-send command is available yet. Implementing one before the controls above would be unsafe.

## Delivery gates and approval

Before seeking send approval: verify the Resend domain and key, make the opt-out endpoint work, reconcile suppression counts, test the private selector against production eligibility without exposing addresses, preview multiple names and neutral greeting, send only to a founder-designated test inbox, verify the delivered CTA and unsubscribe, verify duplicate and failure handling, and record a final eligible count and provider IDs. Do not send to customers during these checks.

As of this review: **no invitation test email and no customer invitation email has been sent**. A test recipient has not been designated. The promotion-specific preference, opt-out, suppression integration, and delivery ledger are not built, so customer sending remains blocked. Founder approval is required after those checks for the actual batch and separately for an optional reminder.

The current [Resend pricing](https://resend.com/pricing) lists a free tier of 3,000 emails per month and 100 per day, with a $20/month Pro tier for 50,000 emails. A batch of roughly 12 invitations would fit the published free quota if the account has sufficient remaining quota; the account's actual plan and available quota have not been verified.
