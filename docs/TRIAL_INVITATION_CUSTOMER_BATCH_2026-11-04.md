# Existing-user trial: one-time customer invitation batch

Status: implementation review only. **No customer sending is authorized.** This change must not be merged, deployed, or enabled without a later founder instruction. The existing claim deadline remains November 15, 2026, 23:59:59 WAT. Flutterwave LIVE stays disabled.

## Scope and safeguards

`apps/api/scripts/send_trial_customer_invitations.py` is an operator-only command for the fixed `existing_user_trial_2026` campaign. It adds no route, schedule, startup task, or database migration. It reuses the private service-only trial status function, candidate selector, Resend audit checks, invitation template, opt-out token, and delivery ledger. No customer address or identifier is printed. The command defaults to preview; it never sends unless `--send` and every gate are present.

Preview verifies the Resend sender domain, SPF/DKIM, quota, current complete suppression list, live campaign window, eligibility, promotional preference and opt-outs, and all existing ledger records for this campaign. A delivered founder test invitation also blocks a customer invitation to the same normalized email. The preview prints aggregates and an HMAC scope value. The HMAC covers the selected owner and normalized-email digest, so a changed recipient set invalidates the operator confirmation without exposing the list.

The send path is limited to 25 recipients, one at a time, at least one second apart. It requires both `TRIAL_INVITATION_SENDING_ENABLED=true` and the new `TRIAL_INVITATION_CUSTOMER_BATCH_ENABLED=true`. The latter defaults to false in code and Render configuration. It requires the exact count and scope from a fresh preview and an exact confirmation string. It checks quota for the whole batch, then the existing delivery path rechecks eligibility, sender, quota, opt-out, and provider suppression immediately before each provider call. The ledger reserves each recipient before sending, serializes concurrent operators, and leaves timeouts or ambiguous responses `uncertain`. `attempting`, `uncertain`, `accepted`, delivered, and other attempted rows are never retried automatically. A prepared row can be resumed after an interruption because no provider call has started.

## Preview (read-only)

Run from `apps/api` in a private operator environment with a verified production PostgreSQL DSN in `GRAVITYOS_TRIAL_INVITE_DSN`, the account-scoped `RESEND_AUDIT_API_KEY`, and the existing `TRIAL_INVITATION_SIGNING_KEY`. Do not put these values in shell history, GitHub, logs, or output artifacts. The audit key must be able to read domains, usage, and the complete suppression list. Keep the production sending flags false for preview.

```sh
python -m scripts.send_trial_customer_invitations --campaign existing_user_trial_2026
```

Record only the aggregate counts, time, and opaque scope in a private approval record. Investigate any unexpected exclusion or provider failure; do not send if the suppression snapshot is incomplete or the campaign window is closed. A count of 12 from a previous checkpoint is historical, not an approval scope.

## Future sending procedure — requires separate founder authorization

1. Complete PR review, CI, deployment review, production smoke checks, and rollback readiness. Confirm account, workspace, plan, claim, and ledger preservation. Confirm Flutterwave routes remain disabled. Keep both sending flags false until a separately authorized sending window.
2. Obtain explicit founder authorization for the fixed campaign, **fresh count and scope**, and one batch. Set the two sending flags in the private operator runtime only for the approved window; do not create a scheduled task or enable sending merely because code is deployed.
3. Rerun preview immediately before sending. If count or scope differs from the approved values, stop and seek a revised approval. Verify the deadline remains open and quota is sufficient.
4. Only then run the command below, substituting the approved aggregate count and opaque scope. Never run it as part of CI or deployment. Do not run the command more than once without inspecting the ledger and obtaining approval for the remaining scope.

```sh
python -m scripts.send_trial_customer_invitations --campaign existing_user_trial_2026 --send --expected-count COUNT --scope SCOPE --confirm 'SEND existing_user_trial_2026 initial COUNT SCOPE'
```

5. Immediately return `TRIAL_INVITATION_CUSTOMER_BATCH_ENABLED` to false. The command reports provider acceptance, not inbox delivery. Reconcile known provider message IDs with `--reconcile`; inspect Resend events and the private ledger for other states. Never blindly retry an `uncertain` or `attempting` row. If a provider call timed out, resolve it against Resend and the ledger manually before any further operation. No automatic retry path exists.

## Incidents and rollback

On suppression, quota, authorization, eligibility, scope, or provider errors, stop the batch; leave sending disabled. A partial run reports only aggregate acceptance and remaining unattempted count. Inspect the private ledger to distinguish `prepared` from `attempting` or `uncertain`. The latter two require manual provider reconciliation and a documented decision; they are excluded from subsequent sends. Rolling back application code does not erase ledger records or opt-outs. Do not delete or reset delivery rows, customer accounts, claims, or preferences to force a resend. If a duplicate or suppressed delivery is suspected, halt the campaign, preserve logs privately, and investigate before any further send.
