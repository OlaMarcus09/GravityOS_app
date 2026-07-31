# Gravity OS - Architecture

Version: 1.1 (MVP Alpha)

Last updated: 2026-07-30

Companion documents: `docs/PRD.md` and `docs/revenue-engine.md`

This document describes the architecture that is currently implemented in the
Gravity OS repository. It is both a technical reference and a status boundary:
features marked **Implemented** exist in the codebase, **Partial** features have
working foundations but are not production-complete, and **Planned** features
remain roadmap work.

## 1. Current Product Status

Gravity OS is a functional MVP alpha. The main creator workflow is implemented
across a Next.js frontend, FastAPI backend, and Supabase database:

- **Implemented:** authentication, profile management, automatic workspace
  provisioning, workspace membership and roles, projects, tasks, calendar,
  release planning, catalogue uploads, budgets, marketing planning, dashboard
  aggregation, plan gating, Gravity Score computation, and provisional manual
  plan administration.
- **Partial:** administration audit history and account controls, team management, billing UX,
  production deployment verification, error-contract consistency, automated
  testing, and milestone-driven dashboard visualization.
- **Planned:** live Stripe subscriptions, live AI Manager generation, email-based
  invitations, offline access, marketplace features, approval workflows, and the
  organization dashboard.

### Architectural decisions

- **Multi-tenant from day one.** Tenant data is scoped to a `workspace` and
  protected by both FastAPI membership checks and Postgres Row Level Security.
- **Online-first.** TanStack Query provides client caching; offline-first sync
  and conflict resolution are deferred.
- **Backend-owned business rules.** FastAPI owns plan limits, privileged writes,
  aggregations, and Gravity Score computation.
- **Supabase-backed identity and data.** Supabase provides Auth, Postgres,
  PostgREST, Row Level Security, and Storage.
- **Direct-to-storage uploads.** Catalogue files upload directly from the browser
  to Supabase Storage using signed URLs created by FastAPI.
- **Plan flags before automated billing.** Free, Pro, and Team behavior is
  enforced today; plan changes are currently performed by a super-admin until
  Stripe is complete.

## 2. Technology Stack

| Layer | Current choice | Status and notes |
|---|---|---|
| Frontend | Next.js 14 App Router, React 18, TypeScript | Client-rendered authenticated product surfaces with responsive desktop/mobile navigation. |
| UI | Custom React primitives and global CSS | The current implementation does not use Tailwind CSS or shadcn/ui. Design tokens live in `apps/web/src/app/globals.css`; shared primitives live in `apps/web/src/components/ui.tsx`. |
| Data fetching | TanStack Query | Query and mutation hooks live in `apps/web/src/lib/queries`. |
| Backend | FastAPI, Pydantic | Resource routers, validation, authorization, plan enforcement, aggregation, and scoring. |
| Database | Supabase Postgres | Schema is managed through versioned SQL migrations. |
| Authentication | Supabase Auth | Browser sessions are forwarded to FastAPI as bearer tokens. |
| Authorization | FastAPI dependencies plus Supabase RLS | Workspace membership, viewer read-only behavior, and plan gates are enforced at the API layer; RLS is the tenant-isolation backstop. |
| File storage | Supabase Storage | Private `catalogue` bucket with signed upload/download URLs. |
| Frontend hosting | Vercel | Configured as the intended Next.js deployment target. |
| Backend hosting | Render | Docker deployment described by `render.yaml`. |

### Runtime topology

```text
Browser
  |
  | Supabase JS: signup, login, session management
  | HTTPS + Bearer JWT + X-Workspace-Id
  v
Next.js application (Vercel)
  |
  | REST /api/v1
  v
FastAPI service (Render)
  |
  | user-scoped Supabase client: normal data access under RLS
  | service-role client: storage signing and privileged administration
  v
Supabase
  |- Auth
  |- Postgres + PostgREST + RLS
  `- Storage
```

The current frontend sends product reads and writes through FastAPI. Although
RLS also permits safe direct client access, direct PostgREST reads are not the
primary application path today.

## 3. Authentication, Tenancy, and Authorization

### Authentication flow

1. The browser signs up or logs in through Supabase Auth.
2. Supabase returns a session and access token.
3. The typed API client attaches the token as
   `Authorization: Bearer <access-token>`.
4. FastAPI verifies the token, extracts the user ID, and creates an auth context.
5. Workspace routes receive `X-Workspace-Id`; FastAPI confirms that the user is
   a member and loads their workspace role and plan.
6. Database queries use a user-scoped Supabase client so RLS evaluates the same
   JWT as the API request.

### JWT verification

The API supports both Supabase signing modes:

- Legacy symmetric tokens are verified with `SUPABASE_JWT_SECRET` and HS256.
- Asymmetric tokens are verified against the Supabase JWKS endpoint. Signing
  keys are cached and refreshed once when a key ID is not found.

### Signup provisioning

Migration `0007_auto_provision_workspace.sql` extends the new-user trigger. A
new Supabase Auth user receives:

- a matching `profiles` row;
- a personal Free workspace; and
- an owner membership for that workspace.

This guarantees that a new account has a valid workspace for API requests.

### Roles

| Role | Read tenant data | Write product data | Manage workspace/members |
|---|---:|---:|---:|
| `owner` | Yes | Yes | Yes |
| `admin` | Yes | Yes | Yes |
| `member` | Yes | Yes | No |
| `viewer` | Yes | No | No |

FastAPI's `require_writer` blocks viewer mutations. Matching RLS policies ensure
that bypassing FastAPI does not grant write access.

### Plans and gates

| Capability | Free | Pro | Team |
|---|---:|---:|---:|
| Active projects | 1 | Unlimited | Unlimited |
| Catalogue items | 25 | Unlimited | Unlimited |
| Tasks and calendar | Yes | Yes | Yes |
| Release planner writes | No | Yes | Yes |
| Budget planner writes | No | Yes | Yes |
| Marketing planner writes | No | Yes | Yes |

Plan limits are enforced in FastAPI. Reads for Pro surfaces remain available so
the UI can render empty states and upgrade messaging, while mutations use the
`require_pro` dependency.

## 4. Data Model

All primary IDs are UUIDs. Tenant-owned rows contain a `workspace_id`, while
child rows such as milestones and budget items inherit tenant ownership through
their parent. Timestamped tables use `created_at` and `updated_at` conventions.

### Identity and tenancy

- **`profiles`** extends `auth.users` with display name, avatar, creative role,
  and timezone.
- **`workspaces`** owns the tenant name, owner, plan, and personal/organization
  type.
- **`workspace_members`** joins users to workspaces with owner, admin, member,
  or viewer roles.

### Core work management

- **`projects`** is the product spine. It stores a creative body of work, its
  type, status, target release date, cover, and description.
- **`tasks`** supports standalone or project-linked work, status, priority, due
  date, assignment, and completion timestamps.
- **`calendar_events`** stores manually created calendar entries. The calendar
  endpoint also derives dates from projects, tasks, campaigns, content pieces,
  and release milestones.

### Pro planning surfaces

- **`release_plans`** stores one structured rollout per project.
- **`release_milestones`** stores ordered production, marketing, distribution,
  and PR steps.
- **`budgets`** stores workspace- or project-level totals and currency.
- **`budget_items`** stores planned and actual spend by category.
- **`campaigns`** stores marketing objectives, dates, and status.
- **`content_pieces`** stores platform-specific planned content and scheduled
  publication dates. Gravity OS plans content but does not publish to social
  networks.

### Catalogue

- **`catalogue_items`** stores metadata for tracks, beats, stems, artwork,
  documents, and videos.
- The database stores a storage path and metadata; binary files live in the
  private Supabase Storage `catalogue` bucket.

### Intelligence

- **`gravity_scores`** stores timestamped overall scores and six dimensions:
  consistency, organization, execution, marketing, collaboration, and business
  readiness.
- **`ai_outputs`** stores structured future AI results such as weekly summaries,
  recommendations, and release-plan suggestions. Retrieval exists; live
  generation does not.

### Relationship summary

```text
profiles --< workspace_members >-- workspaces
                                      |
                +----------+----------+----------+-----------+
                |          |          |          |           |
             projects    tasks   calendar_events budgets   campaigns
                |                     |            |           |
          release_plans          derived dates budget_items content_pieces
                |
        release_milestones

workspaces --< catalogue_items
workspaces --< gravity_scores
workspaces --< ai_outputs
```

## 5. API Architecture

FastAPI exposes REST routes under `/api/v1`. Except for the health probe,
billing webhook, and authentication entry points handled by Supabase, product
requests require a valid bearer token. Tenant routes also require a validated
`X-Workspace-Id` header.

### Implemented routes

```text
Health
  GET    /health

Identity
  GET    /api/v1/me
  PATCH  /api/v1/me

Workspaces and teams
  GET    /api/v1/workspaces
  POST   /api/v1/workspaces
  GET    /api/v1/workspaces/{id}
  PATCH  /api/v1/workspaces/{id}
  GET    /api/v1/workspaces/{id}/members
  POST   /api/v1/workspaces/{id}/members
  PATCH  /api/v1/workspaces/{id}/members/{user_id}
  DELETE /api/v1/workspaces/{id}/members/{user_id}

Projects
  GET    /api/v1/projects
  POST   /api/v1/projects
  GET    /api/v1/projects/{id}
  PATCH  /api/v1/projects/{id}
  DELETE /api/v1/projects/{id}

Tasks
  GET    /api/v1/tasks
  POST   /api/v1/tasks
  PATCH  /api/v1/tasks/{id}
  DELETE /api/v1/tasks/{id}

Unified calendar
  GET    /api/v1/calendar
  POST   /api/v1/calendar/events
  PATCH  /api/v1/calendar/events/{id}
  DELETE /api/v1/calendar/events/{id}

Release planning
  GET    /api/v1/projects/{id}/release-plan
  POST   /api/v1/projects/{id}/release-plan
  PATCH  /api/v1/release-plans/{id}
  POST   /api/v1/release-plans/{id}/milestones
  PATCH  /api/v1/milestones/{id}
  DELETE /api/v1/milestones/{id}

Catalogue
  GET    /api/v1/catalogue
  POST   /api/v1/catalogue
  GET    /api/v1/catalogue/{id}
  PATCH  /api/v1/catalogue/{id}
  DELETE /api/v1/catalogue/{id}

Budgets
  GET    /api/v1/budgets
  POST   /api/v1/budgets
  PATCH  /api/v1/budgets/{id}
  POST   /api/v1/budgets/{id}/items
  PATCH  /api/v1/budget-items/{id}
  DELETE /api/v1/budget-items/{id}

Marketing
  GET    /api/v1/campaigns
  POST   /api/v1/campaigns
  PATCH  /api/v1/campaigns/{id}
  POST   /api/v1/campaigns/{id}/content
  PATCH  /api/v1/content/{id}
  DELETE /api/v1/content/{id}

Dashboard and intelligence
  GET    /api/v1/dashboard
  GET    /api/v1/gravity-score
  POST   /api/v1/gravity-score/compute
  GET    /api/v1/ai/outputs

Super-admin plan management
  GET    /api/v1/workspaces/admin/workspaces
  PATCH  /api/v1/workspaces/admin/workspaces/{workspace_id}/plan
```

### Partial billing routes

```text
POST /api/v1/billing/checkout
GET  /api/v1/billing/portal
POST /api/v1/billing/webhook
```

These contracts are mounted, but Stripe session creation, signature
verification, webhook handling, and subscription-to-workspace synchronization
are not implemented. Without Stripe configuration the routes return HTTP 501.

### Dashboard aggregation

`GET /dashboard` composes a read model from multiple tables rather than owning a
dashboard table. It currently returns:

- tasks due today and overdue;
- upcoming calendar events and release milestones;
- the latest Gravity Score and stored AI output;
- project, task, and catalogue counts; and
- whether the workspace has a release plan.

### Gravity Score

`POST /gravity-score/compute` calculates and stores a snapshot using live
workspace data:

- **Consistency:** recent task completions and calendar activity.
- **Organization:** task due dates, project links, and priority usage.
- **Execution:** task and release-milestone completion rates.
- **Marketing:** campaigns and scheduled/published content.
- **Collaboration:** member count and role diversity.
- **Business readiness:** budgets, catalogue items, release plans, and dated
  projects.

The overall score is a weighted composite of the six dimensions. The model is
implemented but should be treated as an initial product formula requiring
calibration against real user behavior.

### Error contract

The intended application error shape is:

```json
{
  "error": {
    "code": "plan_required",
    "message": "This feature requires a Pro or Team plan",
    "details": null
  }
}
```

Current FastAPI `HTTPException` responses wrap custom details beneath a
top-level `detail` property. The API and frontend error parser must be aligned
before the error shape above can be considered enforced.

## 6. Frontend Architecture

The frontend uses the Next.js App Router with two route groups:

- `(auth)` contains login and signup.
- `(app)` contains the authenticated product shell and feature pages.

The authenticated layout verifies that a Supabase session exists, loads the
current profile and memberships, selects an active workspace, and provides
desktop sidebar and mobile bottom navigation.

### Data layer

- `src/lib/supabase.ts` creates the browser Supabase client.
- `src/lib/api.ts` is the typed FastAPI client. It adds bearer and workspace
  headers and defines request/response types.
- `src/lib/workspace.tsx` holds active workspace, membership, role, plan, and
  read-only state.
- `src/lib/queries` contains TanStack Query hooks and cache invalidation rules
  for each feature.

### Product surfaces

- Landing page and pricing presentation.
- Login and signup flows.
- Dashboard with launch checklist, Gravity Score, priorities, and upcoming work.
- Projects and per-project release plans.
- Task management.
- Unified monthly calendar.
- Catalogue Vault with direct file upload.
- Budget and marketing planners.
- Profile, plan, and workspace-member settings.
- A dedicated, capability-protected platform admin page for workspace search,
  plan metrics, membership counts, and confirmed manual plan changes.

The dashboard release-orbit visualization currently uses static lifecycle nodes;
it does not yet derive stage progress from a selected release plan.

## 7. Repository Layout

```text
GravityOS/
|- docs/
|  |- ARCHITECTURE.md
|  |- PRD.md
|  |- revenue-engine.md
|  `- email-templates/
|- apps/
|  |- web/
|  |  |- src/
|  |  |  |- app/
|  |  |  |  |- (auth)/
|  |  |  |  |- (app)/
|  |  |  |  |- globals.css
|  |  |  |  `- providers.tsx
|  |  |  |- components/ui.tsx
|  |  |  `- lib/
|  |  |     |- api.ts
|  |  |     |- supabase.ts
|  |  |     |- workspace.tsx
|  |  |     `- queries/
|  |  |- package.json
|  |  `- next.config.mjs
|  `- api/
|     |- app/
|     |  |- main.py
|     |  |- core/
|     |  |- routers/
|     |  |- schemas/
|     |  `- services/
|     |- tests/test_smoke.py
|     |- pyproject.toml
|     `- Dockerfile
|- supabase/
|  |- migrations/
|  `- seed.sql
|- render.yaml
`- README/index history from the original landing-page prototype
```

The monorepo keeps frontend, backend, migrations, and product documentation in
one versioned unit while preserving separate deployment targets.

## 8. Deployment and Configuration

### Frontend environment

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_API_URL
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY  # reserved until billing is implemented
```

### Backend environment

```text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET                # required for legacy HS256 projects
SUPABASE_JWT_AUD
CORS_ORIGINS
ENVIRONMENT
STRIPE_SECRET_KEY                  # reserved/partial
STRIPE_WEBHOOK_SECRET              # reserved/partial
SUPER_ADMIN_EMAILS                 # comma-separated verified account emails
```

The frontend is intended for Vercel. The FastAPI service builds from
`apps/api/Dockerfile` and is described as a Render web service in `render.yaml`,
with `/health` used as the liveness endpoint.

## 9. Database Migrations and Security

The migration sequence currently provides:

1. core schema, enums, tables, constraints, indexes, and update triggers;
2. RLS helpers and policies;
3. Auth-to-profile provisioning trigger;
4. hardened function search paths;
5. helper functions moved into the private schema;
6. private catalogue Storage bucket and policies; and
7. automatic personal-workspace provisioning on signup.

Normal product queries use a user-scoped client and remain subject to RLS. The
service-role client bypasses RLS and must remain limited to explicitly
privileged operations such as Storage signing and super-admin administration.

## 10. Known Gaps and Risks

These items describe the current engineering boundary, not completed behavior:

1. **Gravity Score persistence:** the compute endpoint inserts with a
   user-scoped client, while current RLS only defines member read access for
   `gravity_scores`. The write path must use an intentionally privileged service
   operation or receive a safe insert policy.
2. **Error response mismatch:** FastAPI and the frontend parser do not currently
   agree on where custom error data is nested.
3. **Admin audit model:** platform-admin emails are server-configured and the
   frontend consumes an API capability, but plan changes are not yet written to
   an immutable audit log and account suspension/support controls do not exist.
4. **Limited automated tests:** the backend suite currently covers health,
   unauthenticated rejection, and route registration only. There are no
   integration tests for CRUD, RLS, roles, plan gates, uploads, dashboard
   aggregation, or scoring, and no frontend test suite.
5. **Frontend build health:** local typechecking currently fails inside generated
   `.next` types due to a Next.js type-resolution issue. CI and clean-install
   production builds must be made reliable.
6. **Catalogue lifecycle verification:** storage paths are collision-resistant
   and deletion removes the object before metadata, but the binary lifecycle still
   needs verification against the deployed Supabase bucket.
7. **Team invitation verification:** email invitation, pending/acceptance, expiry,
   resend, and revoke flows are implemented but still need deployed end-to-end
   verification with the configured Supabase Auth mailer.
8. **Billing:** pricing and gates exist, but checkout, customer portal, webhook
   verification, and automatic plan lifecycle do not.
9. **AI Manager:** only the storage and retrieval contract exists; there is no LLM
   orchestration, scheduled generation, prompt/version tracking, or cost control.
10. **Operational readiness:** observability, structured logging, rate limiting,
    backups/restore drills, production smoke tests, and documented incident
    procedures are not yet represented in the repository.

## 11. Recommended Delivery Sequence

### Phase 1 - Stabilize the MVP

- Fix Gravity Score persistence and error-shape consistency.
- Move super-admin configuration out of source code.
- Repair clean frontend typecheck/build behavior.
- Add backend feature and permission tests plus a minimal frontend smoke suite.
- Verify all migrations and primary workflows against a clean Supabase project.

### Phase 2 - Complete monetization and teams

- Extend the dedicated admin area with user search, account status controls, and
  immutable audit history. Workspace search, plan management, summary metrics,
  confirmation flows, and responsive loading/error states are implemented.
- Implement Stripe checkout, portal, webhooks, and plan synchronization.
- Verify the email invitation lifecycle and Auth email delivery in production.
- Add Team-specific organization and approval workflows.

### Phase 3 - Product intelligence and expansion

- Calibrate and automate Gravity Score snapshots.
- Implement live AI Manager outputs with provenance, quotas, and review controls.
- Make the dashboard release orbit derive from real milestone progress.
- Add offline capabilities, marketplace functionality, and brand partnerships as
  validated by product demand.

## 12. Definition of Production-Ready MVP

Gravity OS should be considered production-ready when:

- all core Free and Pro workflows pass automated and manual end-to-end tests;
- tenant isolation and role permissions are verified against a clean database;
- frontend and backend builds pass in CI from clean dependency installations;
- billing accurately drives workspace plan state, or billing is explicitly kept
  out of launch with an approved manual operating process;
- privileged configuration is environment-driven and service-role usage is
  audited;
- user-facing errors are consistent and actionable; and
- deployment, monitoring, backup, and rollback procedures are documented and
  exercised.
