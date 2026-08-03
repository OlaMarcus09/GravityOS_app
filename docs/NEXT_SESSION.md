# Next session handoff

Last updated: 2026-08-03

## Repository

- GitHub: `OlaMarcus09/GravityOS_app`
- Active local branch: `master`
- Push product work to the `app` remote, not `origin`.
- Do not add co-author metadata to commits.
- GitHub `main` is the product/deployment branch; `app/master` is stale.
- Latest product commit before this session: `4ce8769 feat: complete team workflow demo readiness`.
- Commit `4ce8769` is pushed to `GravityOS_app/main`; the working tree was clean
  immediately after the push.

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
- `0018_task_approval_completion.sql`

Migrations `0015`, `0016`, and `0017` have been applied in the active Supabase
project. `0017` protects approval columns from direct PostgREST writes, adds
atomic approval RPCs, records approval events, aligns membership RLS with the
API hierarchy, restricts admin invitations to owners, and validates notification
recipients against workspace membership.

Migration `0018` was applied to the active Supabase project on 2026-08-02. It
makes approval atomically complete the task, reopens rejected tasks for
corrections, and protects reviewed-task history from deletion.

## Validation

- API suite: 103 tests passed.
- Frontend typecheck passed after the responsive/onboarding changes.
- Frontend production build passed on Next.js `14.2.35`.
- `git diff --check` passed.
- Playwright smoke coverage is configured for desktop Chrome, iPhone-sized, and
  iPad-sized viewports. The local macOS 11 machine cannot launch current bundled
  Chromium/WebKit binaries (`CATapDescription`/orientation emulation errors), so
  the browser suite must be run in CI or on a current macOS/Windows/Linux host.

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
- Production deployment verified on 2026-08-02: Render and Vercel are live from
  `main`, with production deployments for `4ce8769` and `bad2390` ready.
- Before the next external demo, still run the API `/health`, production CORS,
  invitation-link, and browser network checks against the live URLs.
- Vercel should use the `apps/web` project root and point
  `NEXT_PUBLIC_API_URL` at the deployed Render origin. Deployment status is now
  confirmed in the hosting dashboards.
- The handoff-only commit `bad2390` is the latest `main` commit; product behavior
  is included from `4ce8769`.
- Confirm the deployed web build includes the Admin account support and Plan audit sections.
- The guided Team demo setup and pitch flow are in [docs/DEMO.md](DEMO.md).

## Next work

Start the next session here:

1. Confirm Render and Vercel deploy the new application commit, then run API health,
   production CORS, invitation-link, and browser network checks.
2. Live-test that approval marks a task `Approved · Completed`, while rejection
   reopens it for editing/resubmission and retains the decision history.
3. Run a live two-workspace isolation check and confirm platform-admin support and
   plan-audit sections in production.
4. Seed and rehearse the guided demo workspace for artist managers and label owners.
5. On a current device/browser, verify laptop 1440×900 and 1280×800, iPad portrait
   and landscape, and mobile Safari/Chrome. Use a disposable email to rehearse the
   owner → Admin invitation flow before inviting the artist's real assistant.

The reusable seed, narrative, role setup, approval walkthrough, fallbacks, and
reset checklist are in [docs/DEMO.md](DEMO.md).

Do not start Stripe billing or mobile packaging until the user-testing cycle
produces enough feedback to justify those investments.
