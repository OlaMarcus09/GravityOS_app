# Gravity OS — Architecture

Version: 1.0 (MVP) · Companion to `docs/PRD.md` and `docs/revenue-engine.md`

This document defines the technical foundation for the Gravity OS MVP. It covers the tech stack, data models, API structure, and folder layout. It reflects the following scoping decisions made with the product owner:

- **Multi-tenant from day one.** All data is scoped to a `workspace`. The MVP UI can stay single-user, but the schema supports teams so we avoid a painful migration later.
- **Online-first.** Offline access for notes/tasks is deferred to post-MVP. We rely on standard caching and optimistic UI, not local-first sync.
- **Plan flags, no payments.** We store a plan tier and enforce limits (e.g. Free = 1 active project), but Stripe integration comes later.
- **Gravity Score: schema-ready, compute later.** We store the inputs and a placeholder score record; the scoring algorithm and full dashboard widget are post-MVP.
- **AI Manager: schema-ready, defer calls.** AI outputs (summaries, recommendations) are modeled as stored records. Live LLM calls come post-MVP.
- **Files via Supabase Storage.** Catalogue assets (audio, artwork, contracts) are uploaded to Supabase Storage; the DB stores metadata and the storage path.

---

## 1. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | **Next.js (App Router) + React + TypeScript** | Mobile-first per PRD. Server Components for data-heavy pages, Client Components for interactive planners/calendars. |
| Styling/UI | **Tailwind CSS + shadcn/ui** | Fast, consistent, accessible primitives. Good for the calendar/kanban surfaces. |
| Data fetching | **TanStack Query** | Client-side caching, optimistic updates for task/calendar interactions. |
| Backend | **FastAPI (Python) + Pydantic** | Owns business logic, validation, plan-limit enforcement, and future AI orchestration. |
| Database | **Supabase (Postgres)** | Managed Postgres. Row Level Security (RLS) for workspace isolation. |
| Auth | **Supabase Auth** | JWTs verified by both Next.js and FastAPI. |
| File storage | **Supabase Storage** | Buckets for catalogue assets and contracts, with signed URLs. |
| Frontend hosting | **Vercel** | Native Next.js target. |
| Backend hosting | **Render** | Hosts the FastAPI service (Web Service, Docker runtime). |

### How the pieces talk

```
Browser (Next.js on Vercel)
  │  Supabase JS (auth session, direct reads via RLS where cheap)
  │  fetch() → FastAPI for writes, business logic, aggregations
  ▼
FastAPI (Render)
  │  verifies Supabase JWT
  │  enforces plan limits + workspace membership
  │  Supabase Python client / SQLAlchemy → Postgres
  ▼
Supabase (Postgres + Auth + Storage)
```

**Auth flow.** The browser authenticates with Supabase Auth and holds the session. For any privileged write or aggregation, Next.js calls FastAPI with the Supabase access token in the `Authorization: Bearer` header. FastAPI verifies the JWT signature, resolves the user, checks workspace membership + plan, then executes.

> **JWT verification — confirm signing method.** Supabase supports two token-signing schemes and the correct verification code differs. Check **Supabase → Settings → API → JWT Keys**:
> - **Legacy shared secret (HS256):** matches the current `auth.py`, which verifies with `SUPABASE_JWT_SECRET`. No code change needed.
> - **Asymmetric keys (ES256/RS256):** the current code will *reject all tokens*. `auth.py` must be switched to fetch Supabase's JWKS and verify against the public key.
>
> Reconcile this note (and the "Supabase JWKS" mention under Backend layout below) with whichever scheme the project actually uses before shipping auth.

**Why a separate FastAPI backend instead of Supabase-only?** The Gravity Score, plan-limit enforcement, and the future AI Manager are cross-cutting logic that shouldn't live in the client or in scattered Postgres functions. FastAPI gives us one testable place for it. RLS remains the backstop so a leaked/misused token still can't cross workspace boundaries.

---

## 2. Data Models (MVP)

Conventions: every table has `id uuid pk default gen_random_uuid()`, `created_at timestamptz default now()`, `updated_at timestamptz`. Tenant tables carry `workspace_id uuid not null`. All tenant tables have an RLS policy: a row is visible only if the requesting user is a member of its workspace.

### 2.1 Identity & tenancy

**`profiles`** — extends Supabase `auth.users`.
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | = `auth.users.id` |
| display_name | text | |
| avatar_url | text | |
| creative_role | text | artist / producer / manager / designer… |
| timezone | text | for reminders/calendar |

**`workspaces`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| name | text | |
| owner_id | uuid fk → profiles | |
| plan | text enum | `free` / `pro` / `team` (default `free`) |
| type | text enum | `personal` / `organization` |

**`workspace_members`** — join table for teams/permissions.
| Column | Type | Notes |
|---|---|---|
| workspace_id | uuid fk | |
| user_id | uuid fk → profiles | |
| role | text enum | `owner` / `admin` / `member` / `viewer` |
| invited_at, joined_at | timestamptz | |

*Unique (workspace_id, user_id).* This one table powers all collaboration + RLS.

### 2.2 Projects (the spine)

A **project** is a body of work (a single, an EP, an album, a video, a beat pack). Most features hang off it.

**`projects`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| title | text | |
| type | text enum | `single` / `ep` / `album` / `video` / `beat_pack` / `other` |
| status | text enum | `idea` / `in_progress` / `ready` / `released` / `archived` |
| cover_url | text | Supabase Storage path |
| target_release_date | date | nullable |
| description | text | |
| created_by | uuid fk → profiles | |

Plan limit lives here: Free = at most 1 project with status ≠ `archived` per workspace (enforced in FastAPI).

### 2.3 Task Management

**`tasks`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| project_id | uuid fk → projects | nullable (standalone tasks allowed) |
| title | text | |
| description | text | |
| status | text enum | `todo` / `in_progress` / `blocked` / `done` |
| priority | text enum | `low` / `medium` / `high` |
| due_date | date | nullable |
| assignee_id | uuid fk → profiles | nullable; must be a workspace member |
| created_by | uuid fk → profiles | |
| completed_at | timestamptz | feeds Execution/Consistency scoring |

### 2.4 Creative Calendar

A unified calendar. Entries can be free-standing or linked to a project/task/release. Rather than duplicate dates everywhere, the calendar reads from `calendar_events` plus derived dates (task due dates, release dates) at query time.

**`calendar_events`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| title | text | |
| type | text enum | `content` / `meeting` / `deadline` / `release` / `personal` |
| starts_at | timestamptz | |
| ends_at | timestamptz | nullable |
| all_day | boolean | |
| project_id | uuid fk | nullable |
| notes | text | |

### 2.5 Release Planner (Pro)

A release plan is a structured, staged rollout for a project.

**`release_plans`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| project_id | uuid fk → projects | one active plan per project |
| release_date | date | |
| status | text enum | `draft` / `active` / `completed` |

**`release_milestones`** — ordered steps within a plan.
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| release_plan_id | uuid fk | |
| title | text | e.g. "Submit to distributor", "Announce", "Pre-save live" |
| category | text enum | `production` / `marketing` / `distribution` / `pr` |
| due_date | date | usually relative to release_date |
| status | text enum | `pending` / `done` |
| position | int | ordering |

### 2.6 Catalogue Vault

The creator's library of finished/in-progress assets, with real files in Supabase Storage.

**`catalogue_items`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| project_id | uuid fk | nullable |
| title | text | |
| kind | text enum | `track` / `beat` / `stem` / `artwork` / `document` / `video` |
| status | text enum | `wip` / `final` / `released` |
| isrc | text | nullable, music metadata |
| bpm | int | nullable |
| key | text | nullable, musical key |
| storage_path | text | Supabase Storage object path |
| file_size | bigint | nullable |
| tags | text[] | |

*Plan limit: Free = limited catalogue count (enforced in FastAPI).*

### 2.7 Budget Planner (Pro)

**`budgets`** — one per project or per workspace period.
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| project_id | uuid fk | nullable |
| name | text | |
| total_amount | numeric(12,2) | planned total |
| currency | text | e.g. `NGN`, `USD` |

**`budget_items`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| budget_id | uuid fk | |
| category | text enum | `production` / `marketing` / `visuals` / `distribution` / `other` |
| label | text | |
| planned_amount | numeric(12,2) | |
| actual_amount | numeric(12,2) | nullable |
| spent_at | date | nullable |

### 2.8 Marketing Planner (Pro)

**`campaigns`**
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| project_id | uuid fk | nullable |
| name | text | |
| objective | text enum | `awareness` / `engagement` / `conversion` / `release_hype` |
| status | text enum | `planned` / `active` / `completed` |
| start_date, end_date | date | |

**`content_pieces`** — planned posts/assets within a campaign.
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| campaign_id | uuid fk | |
| workspace_id | uuid fk | |
| platform | text enum | `instagram` / `tiktok` / `x` / `youtube` / `other` |
| format | text enum | `post` / `reel` / `story` / `video` / `other` |
| scheduled_at | timestamptz | surfaces on the Creative Calendar |
| status | text enum | `idea` / `drafted` / `scheduled` / `published` |
| caption | text | |

*No actual social publishing in MVP (out of scope per PRD) — this is planning only.*

### 2.9 Dashboard

The Dashboard has **no table of its own.** It's an aggregation endpoint that reads across tasks (due today/overdue), calendar (upcoming), release milestones, and the latest Gravity Score / AI summary. Kept as a read model so "what deserves attention today" stays a single fast call.

### 2.10 Gravity Score™ (schema-ready)

**`gravity_scores`** — one row per workspace per snapshot.
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| computed_at | timestamptz | |
| overall | int | 0–100 (nullable until compute lands) |
| consistency, organization, execution, marketing, collaboration, business_readiness | int | six dimensions, 0–100 |

The MVP writes a placeholder row; the algorithm that fills these from the underlying tables is post-MVP.

### 2.11 AI Manager (schema-ready)

**`ai_outputs`** — stored generations (weekly summaries, recommendations).
| Column | Type | Notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid fk | |
| kind | text enum | `weekly_summary` / `recommendation` / `release_plan_suggestion` |
| payload | jsonb | structured output |
| generated_at | timestamptz | |
| model | text | nullable, for later provenance |

No live LLM calls in MVP; this table + endpoints are stubbed so the UI and contract exist.

### Entity relationships (summary)

```
profiles ──< workspace_members >── workspaces
                                      │
        ┌───────────────┬────────────┼───────────────┬──────────────┐
     projects        tasks      calendar_events   catalogue_items  campaigns
        │               │                               │              │
  release_plans   (assignee_id→profiles)           storage files  content_pieces
        │
  release_milestones

workspaces ──< budgets ──< budget_items
workspaces ──< gravity_scores
workspaces ──< ai_outputs
```

---

## 3. API Structure

REST over `/api/v1`, served by FastAPI. Every route requires a valid Supabase JWT and resolves the active workspace via an `X-Workspace-Id` header (validated against `workspace_members`). Standard verbs, plural nouns, cursor/offset pagination on list endpoints.

### Resource routes

```
Auth / identity
  GET   /api/v1/me                      → profile + memberships

Workspaces & teams
  GET   /api/v1/workspaces
  POST  /api/v1/workspaces
  GET   /api/v1/workspaces/{id}
  PATCH /api/v1/workspaces/{id}
  GET   /api/v1/workspaces/{id}/members
  POST  /api/v1/workspaces/{id}/members        (invite)
  PATCH /api/v1/workspaces/{id}/members/{uid}  (role change)
  DELETE/api/v1/workspaces/{id}/members/{uid}

Projects
  GET   /api/v1/projects
  POST  /api/v1/projects                (enforces Free = 1 active project)
  GET   /api/v1/projects/{id}
  PATCH /api/v1/projects/{id}
  DELETE/api/v1/projects/{id}

Tasks
  GET   /api/v1/tasks?project_id=&status=&assignee_id=&due_before=
  POST  /api/v1/tasks
  PATCH /api/v1/tasks/{id}
  DELETE/api/v1/tasks/{id}

Calendar
  GET   /api/v1/calendar?from=&to=       → merged events + derived task/release dates
  POST  /api/v1/calendar/events
  PATCH /api/v1/calendar/events/{id}
  DELETE/api/v1/calendar/events/{id}

Release planner
  GET   /api/v1/projects/{id}/release-plan
  POST  /api/v1/projects/{id}/release-plan
  PATCH /api/v1/release-plans/{id}
  POST  /api/v1/release-plans/{id}/milestones
  PATCH /api/v1/milestones/{id}
  DELETE/api/v1/milestones/{id}

Catalogue
  GET   /api/v1/catalogue?project_id=&kind=&status=
  POST  /api/v1/catalogue                (returns signed upload URL for Storage)
  GET   /api/v1/catalogue/{id}           (returns signed download URL)
  PATCH /api/v1/catalogue/{id}
  DELETE/api/v1/catalogue/{id}

Budget
  GET   /api/v1/budgets?project_id=
  POST  /api/v1/budgets
  PATCH /api/v1/budgets/{id}
  POST  /api/v1/budgets/{id}/items
  PATCH /api/v1/budget-items/{id}
  DELETE/api/v1/budget-items/{id}

Marketing
  GET   /api/v1/campaigns?project_id=&status=
  POST  /api/v1/campaigns
  PATCH /api/v1/campaigns/{id}
  POST  /api/v1/campaigns/{id}/content
  PATCH /api/v1/content/{id}
  DELETE/api/v1/content/{id}

Dashboard & intelligence
  GET   /api/v1/dashboard                → aggregated "today" view
  GET   /api/v1/gravity-score            → latest snapshot (placeholder in MVP)
  GET   /api/v1/ai/outputs?kind=         → stored AI outputs (stubbed in MVP)
```

### Cross-cutting concerns

- **Auth middleware** verifies the JWT signature (see the JWT verification note in the Auth flow section) and loads the user once per request.
- **Workspace guard** dependency confirms membership and attaches `role` for permission checks (viewers are read-only).
- **Plan-limit dependency** checks `workspace.plan` before create operations gated by tier (projects, catalogue count, Pro-only features).
- **File uploads** never stream through FastAPI: the API returns a Supabase Storage **signed upload URL**; the browser uploads directly, then confirms metadata via `POST /catalogue`.
- **Errors** return a consistent shape: `{ "error": { "code", "message", "details" } }`.

---

## 4. Folder Structure

A monorepo keeps the frontend and backend versioned together while deploying to different platforms.

```
GravityOS/
├── docs/
│   ├── PRD.md
│   └── revenue-engine.md
├── ARCHITECTURE.md
│
├── apps/
│   ├── web/                        # Next.js → Vercel
│   │   ├── app/
│   │   │   ├── (auth)/             # login, signup
│   │   │   ├── (app)/              # authenticated shell
│   │   │   │   ├── dashboard/
│   │   │   │   ├── calendar/
│   │   │   │   ├── tasks/
│   │   │   │   ├── projects/
│   │   │   │   │   └── [id]/release-plan/
│   │   │   │   ├── catalogue/
│   │   │   │   ├── budget/
│   │   │   │   └── marketing/
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn primitives
│   │   │   ├── calendar/
│   │   │   ├── tasks/
│   │   │   └── shared/
│   │   ├── lib/
│   │   │   ├── api.ts              # typed FastAPI client
│   │   │   ├── supabase.ts         # browser client
│   │   │   └── queries/            # TanStack Query hooks
│   │   ├── types/                  # shared TS types (mirror API schemas)
│   │   ├── public/
│   │   ├── package.json
│   │   └── next.config.ts
│   │
│   └── api/                        # FastAPI → Render
│       ├── app/
│       │   ├── main.py             # app factory, router mounting
│       │   ├── core/
│       │   │   ├── config.py       # env/settings
│       │   │   ├── auth.py         # JWT verification
│       │   │   ├── deps.py         # workspace guard, plan-limit deps
│       │   │   └── db.py           # Supabase/Postgres client
│       │   ├── models/             # SQLAlchemy or Supabase table models
│       │   ├── schemas/            # Pydantic request/response
│       │   ├── routers/
│       │   │   ├── workspaces.py
│       │   │   ├── projects.py
│       │   │   ├── tasks.py
│       │   │   ├── calendar.py
│       │   │   ├── releases.py
│       │   │   ├── catalogue.py
│       │   │   ├── budgets.py
│       │   │   ├── marketing.py
│       │   │   ├── dashboard.py
│       │   │   └── intelligence.py # gravity score + ai (stubs)
│       │   └── services/           # business logic (plan limits, aggregation, future scoring/AI)
│       ├── tests/
│       ├── pyproject.toml
│       └── Dockerfile              # Render build
│
├── packages/
│   └── shared-types/               # optional: OpenAPI-generated types shared web↔api
│
└── supabase/
    ├── migrations/                 # SQL migrations (schema + RLS policies)
    └── seed.sql
```

**Why this layout.** The `apps/web` and `apps/api` split mirrors the two deploy targets (Vercel, Render) cleanly. `supabase/migrations` is the single source of truth for schema and RLS, kept in git so the DB is reproducible. `packages/shared-types` (optional) lets us generate TypeScript from the FastAPI OpenAPI spec so the frontend and backend never drift.

---

## 5. Open Items for Post-MVP

Tracked here so they're not lost, but explicitly out of the MVP build:

- Stripe billing + subscription lifecycle (webhooks, upgrades/downgrades).
- Offline access for notes/tasks (local-first sync + conflict resolution).
- Gravity Score compute engine + dashboard visualization.
- Live AI Manager (LLM orchestration behind the `ai_outputs` contract).
- Marketplace (service commissions, vetted professional profiles) and Brand Partnerships — from `revenue-engine.md`, not part of the core MVP surface.
- Approval workflows and organization dashboard for the Team plan.

