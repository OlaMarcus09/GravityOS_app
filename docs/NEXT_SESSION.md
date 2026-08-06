# Next session handoff

Last updated: 2026-08-06

## Repository

- GitHub: `OlaMarcus09/GravityOS_app`
- Active local branch: `master`
- Push product work to the `app` remote, not `origin`.
- Do not add co-author metadata to commits.
- GitHub `main` is the product/deployment branch; `app/master` is stale.
- Foundation commit: `c510bcb feat: add enterprise and proactive notification foundations`.
- Pilot readiness commit: `0fae318 feat: finish pilot notification and pwa readiness`.
- Mobile PWA layout fix: `2bd9553 fix: stabilize mobile comments and notifications`.
- Manual Soundcharts sync: `c723076 feat: enable manual soundcharts metric sync`.
- Empty Soundcharts connection fix: `2c4018c fix: handle empty soundcharts connections`.
- Security hardening: `351e60f security: harden plans uploads and runtime`.
- Workspace ownership trigger fix: `b51bc4f fix: protect workspace ownership updates`.
- The free GitHub Actions scheduler replacement follows that foundation; no paid
  Render cron job is required.

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
- Installable PWA metadata, safe service-worker registration, and a static
  offline fallback without caching authenticated workspace data.
- Task approval workflow for Team workspaces.
- Immutable approval event history and server-side approval transitions.
- Admin plan audit history, user search, suspension, and reactivation.
- Cross-workspace reference validation and database tenancy guards.
- Manager-facing approval review queue with review notes and decision context.
- Task-specific notification links that focus the affected task.
- Persistent desktop/mobile notification chrome with accessible dismissal.
- Stale email-delivery lease recovery so interrupted workers cannot strand mail.
- Professional notification email footers link directly to Settings preferences.
- Soundcharts artist connection, cost-controlled manual current-stats sync, and
  a responsive stored-snapshot analytics dashboard for every workspace plan.
- GitHub Actions CI for the full API suite, frontend typecheck/build, and
  Playwright smoke checks across desktop, mobile, and tablet viewports.
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
- `0018_task_approval_completion.sql`
- `0019_enterprise_plan.sql` (applied 2026-08-05)
- `0020_enterprise_foundations.sql` (applied 2026-08-05)
- `0021_proactive_notifications.sql` (applied 2026-08-05)
- `0022_plan_enforcement.sql` (applied 2026-08-06)
- `0023_catalogue_storage_limits.sql` (applied 2026-08-06)

Migrations `0015`, `0016`, and `0017` have been applied in the active Supabase
project. `0017` protects approval columns from direct PostgREST writes, adds
atomic approval RPCs, records approval events, aligns membership RLS with the
API hierarchy, restricts admin invitations to owners, and validates notification
recipients against workspace membership.

Migration `0018` was applied to the active Supabase project on 2026-08-02. It
makes approval atomically complete the task, reopens rejected tasks for
corrections, and protects reviewed-task history from deletion.

Migrations `0019`, `0020`, and `0021` are applied in production. They add the
reserved Enterprise enum value, organization membership and owner-opt-in
workspace links, read-only organization access to six approved workspace tables,
Soundcharts identity/snapshot storage, notification preferences, and a
service-owned email outbox. Soundcharts reads are available to every direct
workspace member regardless of plan; plan gating is deferred. The production
database has older timestamped migration-history entries from earlier manual
deployments; the three new migrations were applied directly and recorded in the
history table without rewriting those entries.

Migrations `0022` and `0023` were applied in production on 2026-08-06. They
enforce Free-plan limits and paid-feature writes at the database boundary and
cap the Catalogue Storage bucket at 500 MB.

## Validation

- API suite: 149 tests passed, including 8/8 focused streaming tests.
- Frontend typecheck passed after the responsive/onboarding changes.
- Frontend production build compiled, validated types, and generated all 21 routes
  on Next.js `16.3.0`, including `/analytics`.
- `git diff --check` passed.
- Playwright smoke coverage is configured for desktop Chrome, iPhone-sized, and
  iPad-sized viewports. The local macOS 11 machine cannot launch current bundled
  Chromium/WebKit binaries (`CATapDescription`/orientation emulation errors), so
  the browser suite must be run in CI or on a current macOS/Windows/Linux host.
- Focused approval, permission, invitation, and migration-contract checks passed:
  74 tests.

## Responsive and onboarding hardening completed

- Mobile navigation now exposes Dashboard, Calendar, Tasks, Projects, and a
  dismissible More sheet for secondary areas.
- Small laptop/iPad widths use a compact icon sidebar without changing desktop
  navigation.
- Calendar switches to an agenda on phones, including events, task due dates,
  releases, campaigns, scheduled content, and milestones.
- Shared modals lock background scroll, support Escape, safe areas, internal
  scrolling, and mobile bottom-sheet behavior; form controls avoid Safari zoom.
- Login supports safe `?next=` redirects; signup handles confirmation-required
  Supabase projects; invite acceptance surfaces errors and completes cleanly.
- Next.js is pinned to patched `14.2.35`; Playwright smoke scripts are in
  `apps/web/tests/e2e`.

## Deployment configuration

- Render API has `SUPER_ADMIN_EMAILS` configured with the verified platform admin email.
- The custom domain is live at `https://www.gravityos.tech`; the apex redirects
  to `www`. Render health reports `production`, and CORS is verified for both
  custom-domain origins.
- Before the next external demo, still run the API `/health`, production CORS,
  invitation-link, and browser network checks against the live URLs.
- Vercel should use the `apps/web` project root and point
  `NEXT_PUBLIC_API_URL` at the deployed Render origin. Deployment status is now
  confirmed in the hosting dashboards.
- The local `apps/web/.env` still points at `http://localhost:8000`; do not treat
  local health failures as production failures.
- Confirm the deployed web build includes the Admin account support and Plan audit sections.
- The guided Team demo setup and pitch flow are in [docs/DEMO.md](DEMO.md).

## Next work

Start the next session here:

1. Confirm Vercel and Render deploy through `2c4018c`, then retest the iOS task
   comment keyboard layout, compact Android notification panel, PWA manifest,
   notification task links, preference feedback, and email worker health.
2. Open the dedicated Soundcharts Analytics page after a manual sync and verify
   latest signals, metric/platform filters, and responsive trend charts. A 401/403
   from sync means the account does not include the premium current-stats endpoint.
3. Confirm the first `CI` workflow run is green in GitHub Actions. Keep the
   notification-reminder workflow separate; it continues running every five minutes.
4. Once the current ISP/Vercel routing issue is bypassed, run API health, production CORS,
   invitation-link, and browser network checks against the actual dashboard URLs.
5. Send a disposable-account assignment, mention, approval, and due-date reminder;
   confirm one in-app record and one professional email for each enabled event.
6. Live-test that approval marks a task `Approved · Completed`, while rejection
   reopens it for editing/resubmission and retains the decision history.
7. Run a live two-workspace isolation check and confirm platform-admin support and
   plan-audit sections in production.
8. Seed and rehearse the guided demo workspace for artist managers and label owners.
9. On a current device/browser, verify laptop 1440×900 and 1280×800, iPad portrait
   and landscape, and mobile Safari/Chrome. Use a disposable email to rehearse the
   owner → Admin invitation flow before inviting the artist's real assistant.
10. If production is green, run the complete pilot rehearsal: Owner creates task →
   team member submits → Admin reviews → approval completes the task, while
   rejection reopens it for correction and resubmission.

The reusable seed, narrative, role setup, approval walkthrough, fallbacks, and
reset checklist are in [docs/DEMO.md](DEMO.md).

Do not start Stripe billing or mobile packaging until the user-testing cycle
produces enough feedback to justify those investments.
