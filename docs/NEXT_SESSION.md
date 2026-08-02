# Next session handoff

Last updated: 2026-08-02

## Repository

- GitHub: `OlaMarcus09/GravityOS_app`
- Active local branch: `master`
- Push product work to the `app` remote, not `origin`.
- Do not add co-author metadata to commits.
- GitHub `main` is the product/deployment branch; `app/master` is stale.
- The current product batch is validated and ready to commit to `app/main`.

## Product direction

Billing and mobile apps are deferred while early users test the product.
The current pitch target is artist managers, label owners, and creative teams.
The team product story is shared workspaces, role-based access, assignments,
comments, approval control, notifications, and an accountable activity history.

## Completed team capabilities

- Workspace invitation lifecycle, acceptance, resend, expiry, and revoke.
- Team members with owner, admin, member, and viewer roles.
- Owner/admin membership protections and viewer read-only enforcement.
- Projects, tasks, assignments, comments, mentions, and activity feed.
- Persistent notifications and invitation/assignment/mention alerts.
- Task approval workflow for Team workspaces.
- Immutable approval event history and server-side approval transitions.
- Admin plan audit history, user search, suspension, and reactivation.
- Cross-workspace reference validation and database tenancy guards.
- Manager-facing approval review queue with review notes and decision context.
- Verified member email display and filterable workspace activity.

## Supabase migrations

- `0010_notifications.sql`
- `0011_collaboration.sql`
- `0012_owner_membership_guards.sql`
- `0013_tenant_reference_integrity.sql`
- `0014_security_hardening.sql`
- `0015_admin_plan_audit.sql`
- `0016_task_approvals.sql`
- `0017_team_workflow_integrity.sql`

Migrations `0015`, `0016`, and `0017` have been applied in the active Supabase
project. `0017` protects approval columns from direct PostgREST writes, adds
atomic approval RPCs, records approval events, aligns membership RLS with the
API hierarchy, restricts admin invitations to owners, and validates notification
recipients against workspace membership.

## Validation

- API suite: 97 tests passed.
- Frontend typecheck passed.
- Frontend production build passed.
- `git diff --check` passed.

## Deployment configuration

- Render API has `SUPER_ADMIN_EMAILS` configured with the verified platform admin email.
- Before the next external demo, verify the deployed commit, `/health`, production
  `CORS_ORIGINS`, and `WEB_APP_URL`; these are managed Render variables.
- Vercel should use the `apps/web` project root and point
  `NEXT_PUBLIC_API_URL` at the deployed Render origin. Deployment status has not
  been independently verified from this workstation.
- Redeploy API and web after committing the current product batch.
- Confirm the deployed web build includes the Admin account support and Plan audit sections.
- The guided Team demo setup and pitch flow are in [docs/DEMO.md](DEMO.md).

## Next work

1. Push the validated product batch to `app/main`.
2. Verify Render and Vercel deployed the resulting commit and run the health/CORS checks.
3. Live-test Team approvals with separate member, owner/admin, and viewer accounts.
4. Run a live two-workspace isolation check using dedicated test accounts.
5. Seed and rehearse the guided demo workspace for artist managers and label owners.

The reusable seed, narrative, role setup, approval walkthrough, fallbacks, and
reset checklist are in [docs/DEMO.md](DEMO.md).

Do not start Stripe billing or mobile packaging until the user-testing cycle
produces enough feedback to justify those investments.
