# Seven-day Pro trial release

This release gives eligible new workspaces 168 hours of Pro without a card or automatic charge. Paid checkout, payment verification, payment portals, and payment webhooks return `503 billing_checkout_disabled`. No provider integration is included in this release. Enabling an environment variable alone cannot enable payment collection.

## Entitlements

- A confirmed account created during the enrollment window can claim one trial, on its first eligible Free workspace. The database records the start and an expiry exactly 168 hours later. Later workspaces cannot claim again.
- Claims are unique by owner and normalized email digest and survive account/workspace deletion. Public enrollment is controlled by `private.founder_trial_campaign`; it starts disabled.
- The stored workspace plan stays Free. The API computes the effective plan on each request, and database feature gates and Free limits use `clock_timestamp()`. Expiry requires no scheduled job.
- Expiry prevents new Pro writes and restores Free limits. Existing projects, tasks, release plans, catalogue items, and other workspace data stay stored and readable.
- Manual grants and valid paid entitlements take precedence. An explicit administrator plan decision clears trial dates and retains the consumed claim. Migration `0031` records the prior trial expiry so revoking a stored-Free trial is a valid immutable audit event.
- Email confirmation and signup protections remain enabled. Different verified email identities can obtain separate card-free trials; owner/email uniqueness does not identify a person across unrelated accounts.

## Preconditions

1. Confirm the product remote is `app`, repository `OlaMarcus09/GravityOS_app`, deployment branch `main`, and production Supabase project `hopleyvbxiuksxxucozg`. Development is `wgdvzsplkaakfjppdlxd`; do not create another project.
2. Inspect the actual production history and schema. The historical `0009–0018` records are absent even though their schema effects are installed. Compare function bodies, security modes/search paths, policies, indexes, constraints, columns, triggers, and grants to the reviewed migrations through `0025`. Preserve the original history; do not replay installed migrations or invent execution dates.
3. Capture a PostgreSQL 17-compatible consistent backup, migration history, roles without role passwords, and Storage object bytes/metadata. Keep backups outside Git with owner-only permissions. Restore into a private local PostgreSQL 17 cluster with matching extensions, then verify every table's row count and canonical data hash, history, and Storage file hashes. Match the production bootstrap superuser (`supabase_admin`, OID 10) when restoring original role grantors. Verify Vault key recovery separately if Vault contains secrets. Supabase may run its own Storage migrations on a Storage request; if its history changes during backup, stop the release gate, verify the provider's recorded source hash and complete schema effects, and capture and restore a fresh snapshot.
4. Record live Render/Vercel commit and deployment IDs, production targets, build commands, environment variable names and safe values, and recovery controls. Never print or publish credentials. Render must have no Flutterwave credentials, and `BILLING_CHECKOUT_ENABLED` must be absent or false. Its application default is false.
5. Review the exact release diff and commit parents. Exclude development payment code, checkout concurrency changes, local credentials, test accounts, temporary evidence, and unrelated edits. Run API tests, frontend typecheck/build, dependency audit, and relevant browser/database checks on that release.

Stop before production writes if any prerequisite fails. Do not force migrations, reset the database, or silently repair existing data.

## Reviewed migration dependencies

| Migration | Why the trial needs it |
| --- | --- |
| `0026_billing_foundation.sql` | Adds the entitlement fields used by the tested trial implementation. Existing Pro/Team/Enterprise plans are classified as manual without changing their stored plan. The existing updated-at trigger runs for those classifications. |
| `0028_protect_billing_entitlements.sql` | Protects workspace creation and administrator grants. Review its manual-classification update and affected rows explicitly. |
| `0029_founder_pro_trial.sql` | Adds disabled enrollment, one-use claims, trial timestamps, and clock-based API/database entitlement support. Depends on the billing fields and existing plan-enforcement/audit foundations. |
| `0030_founder_trial_pgcrypto_path.sql` | Resolves `digest` from Supabase's `extensions` schema. Enrollment must remain disabled until this is installed. |
| `0031_audit_trial_revocation.sql` | Preserves an immutable audit when revocation changes an effective Pro trial to Free while its stored plan remains Free. |

`0027_billing_checkout_concurrency.sql` is a payment-only index, has no trial dependents, and is deferred to the separate payment release. Do not edit migrations already applied to development.

Apply the reviewed migration files in the order above, in one transaction with bounded lock/statement timeouts. Verify the expected prior history/schema, dependencies, source hashes, and data baseline first. Record only newly executed migrations in `supabase_migrations.schema_migrations`, verify each step and the final disabled campaign, and commit only if all checks pass. Any error rolls back the transaction and stops the release. Do not use a blind CLI push against the known historical gaps.

## Deployment order

1. Keep enrollment disabled. Push the reviewed backend commit, including the required Next.js security dependency update, to `app/main`. Its new API reads require the migrations; the existing frontend flow remains compatible. Wait for matching Render and Vercel deployments and verify `/health`, `/health/ready`, authentication, existing Free/manual workspace access, and disabled payment routes.
2. Record the immediately previous READY Vercel deployment and current Render deployment. Push the reviewed frontend commit, whose parent is the verified backend commit. Confirm Vercel and Render are serving the expected commit, and that the public browser build points to production Supabase and `https://gravityos-app.onrender.com`.
3. Verify the public website, signup/login pages, API/CORS, Settings, trial notices, and absence of card fields and checkout actions. Leave enrollment disabled during all pre-enrollment smoke checks.

## Disposable-account smoke procedure

1. Use new aliases of a founder-controlled, deliverable test email. Create accounts through public signup and verify login after confirmation. Store test credentials and IDs only in private local evidence. Never reset a real account's password or alter its entitlements.
2. To test automatic trial claims before public enrollment, use one transaction that temporarily enables a campaign window containing only the test account's eligibility time, confirms the specifically identified disposable account to exercise the confirmation trigger, and restores the original disabled campaign row before commit. The enabled value is never visible to other sessions. If confirmation already occurred, resetting/reconfirming is permitted only for that disposable fixture in the same transaction. Confirm the public campaign remains disabled after commit.
3. Verify the default workspace's stored Free plan, effective Pro plan, exact 604800-second duration, and Pro feature writes. Create a second workspace and verify it cannot claim again. Use a second disposable owner to check API and direct database workspace isolation.
4. Preserve the trial's original dates. Move only that disposable workspace's dates into the past using one database timestamp and the same 168-hour interval. Verify API and database rejection of new Pro writes, Free project limits, and continued access to existing projects, release plans, tasks, and comments. Restore the original fixture dates. Never modify a system clock or a real customer's entitlement.
5. Compare existing users/workspaces/data and all prior manual plan grants to the baseline. Test existing-account reads without changing account state. Check that payment endpoints reject requests without creating transactions, and inspect the frontend for payment/card collection. Do not send payment webhooks or contact a payment provider.
6. If every check passes, enable the production campaign in one transaction with a single `clock_timestamp()` start and an end 168 hours later. Record both UTC timestamps. Confirm a new signup after that start receives a full seven-day trial through the normal confirmation path. The enrollment window bounds new claims; each claim retains its own full 168 hours.

## Recovery

- Stop new claims by setting `private.founder_trial_campaign.enabled=false`. This switch does not revoke existing trials. The enrollment end also prevents new claims automatically.
- On a critical smoke failure, stop rollout and disable enrollment before recovery. Keep the additive schema, claim records, customer data, and migration history intact.
- Vercel Hobby supports instant rollback to the immediately previous production deployment. Record that ID before each push; an intervening backend-only deployment contains the previous frontend. Verify the rollback and public health.
- The supplied Render API key is authorized for inspection only. Do not use it to change settings or invoke a rollback. The authorized recovery path is a reviewed Git revert of the release commits on `app/main`, followed by the verified automatic Render deployment. Confirm the replacement deployment's commit and readiness. A founder can also use Render's native rollback when the recorded artifact is retained; do not assume retention from an old deployment record alone.
- Before reverting an API that understands trials after enrollment has opened, identify active claims and explicitly preserve or account for those entitlements. During pre-enrollment verification, only disposable fixtures should hold claims.
- Use the verified database backup only for a serious database failure, after accounting for writes since its snapshot. Rehearsal is local; do not reset production or drop billing/trial data as an application rollback shortcut. Retain Storage bytes and the corresponding metadata together.

Flutterwave LIVE payments require separate explicit authorization and a separate reviewed release.
