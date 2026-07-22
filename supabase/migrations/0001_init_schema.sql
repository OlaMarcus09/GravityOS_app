-- Gravity OS — initial schema
-- Section 2 of docs/ARCHITECTURE.md
-- Covers identity/tenancy, projects, tasks, calendar, releases, catalogue,
-- budget, marketing, and schema-ready gravity_scores + ai_outputs.
--
-- Conventions (per ARCHITECTURE.md section 2):
--   id uuid pk default gen_random_uuid()
--   created_at timestamptz default now()
--   updated_at timestamptz (maintained by trigger below)
--   tenant tables carry workspace_id uuid not null

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists "pgcrypto";  -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
create type workspace_plan       as enum ('free', 'pro', 'team');
create type workspace_type       as enum ('personal', 'organization');
create type member_role          as enum ('owner', 'admin', 'member', 'viewer');
create type project_type         as enum ('single', 'ep', 'album', 'video', 'beat_pack', 'other');
create type project_status       as enum ('idea', 'in_progress', 'ready', 'released', 'archived');
create type task_status          as enum ('todo', 'in_progress', 'blocked', 'done');
create type task_priority        as enum ('low', 'medium', 'high');
create type calendar_event_type  as enum ('content', 'meeting', 'deadline', 'release', 'personal');
create type release_plan_status  as enum ('draft', 'active', 'completed');
create type milestone_category   as enum ('production', 'marketing', 'distribution', 'pr');
create type milestone_status     as enum ('pending', 'done');
create type catalogue_kind       as enum ('track', 'beat', 'stem', 'artwork', 'document', 'video');
create type catalogue_status     as enum ('wip', 'final', 'released');
create type budget_category      as enum ('production', 'marketing', 'visuals', 'distribution', 'other');
create type campaign_objective   as enum ('awareness', 'engagement', 'conversion', 'release_hype');
create type campaign_status      as enum ('planned', 'active', 'completed');
create type content_platform     as enum ('instagram', 'tiktok', 'x', 'youtube', 'other');
create type content_format       as enum ('post', 'reel', 'story', 'video', 'other');
create type content_status       as enum ('idea', 'drafted', 'scheduled', 'published');
create type ai_output_kind       as enum ('weekly_summary', 'recommendation', 'release_plan_suggestion');

-- ---------------------------------------------------------------------------
-- updated_at trigger helper
-- ---------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ===========================================================================
-- 2.1 Identity & tenancy
-- ===========================================================================

-- profiles extends auth.users (id = auth.users.id)
create table profiles (
  id            uuid primary key references auth.users (id) on delete cascade,
  display_name  text,
  avatar_url    text,
  creative_role text,
  timezone      text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz
);

create table workspaces (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  owner_id   uuid not null references profiles (id) on delete restrict,
  plan       workspace_plan not null default 'free',
  type       workspace_type not null default 'personal',
  created_at timestamptz not null default now(),
  updated_at timestamptz
);
create index idx_workspaces_owner on workspaces (owner_id);

create table workspace_members (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  user_id      uuid not null references profiles (id) on delete cascade,
  role         member_role not null default 'member',
  invited_at   timestamptz,
  joined_at    timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz,
  unique (workspace_id, user_id)
);
create index idx_workspace_members_user on workspace_members (user_id);
create index idx_workspace_members_ws   on workspace_members (workspace_id);

-- ===========================================================================
-- 2.2 Projects (the spine)
-- ===========================================================================
create table projects (
  id                  uuid primary key default gen_random_uuid(),
  workspace_id        uuid not null references workspaces (id) on delete cascade,
  title               text not null,
  type                project_type not null default 'single',
  status              project_status not null default 'idea',
  cover_url           text,
  target_release_date date,
  description         text,
  created_by          uuid references profiles (id) on delete set null,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz
);
create index idx_projects_workspace on projects (workspace_id);
create index idx_projects_status    on projects (workspace_id, status);

-- ===========================================================================
-- 2.3 Task Management
-- ===========================================================================
create table tasks (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  project_id   uuid references projects (id) on delete set null,
  title        text not null,
  description  text,
  status       task_status not null default 'todo',
  priority     task_priority not null default 'medium',
  due_date     date,
  assignee_id  uuid references profiles (id) on delete set null,
  created_by   uuid references profiles (id) on delete set null,
  completed_at timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_tasks_workspace on tasks (workspace_id);
create index idx_tasks_project   on tasks (project_id);
create index idx_tasks_assignee  on tasks (assignee_id);
create index idx_tasks_due       on tasks (workspace_id, due_date);

-- ===========================================================================
-- 2.4 Creative Calendar
-- ===========================================================================
create table calendar_events (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  title        text not null,
  type         calendar_event_type not null default 'personal',
  starts_at    timestamptz not null,
  ends_at      timestamptz,
  all_day      boolean not null default false,
  project_id   uuid references projects (id) on delete set null,
  notes        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_calendar_workspace on calendar_events (workspace_id);
create index idx_calendar_range     on calendar_events (workspace_id, starts_at);

-- ===========================================================================
-- 2.5 Release Planner
-- ===========================================================================
create table release_plans (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  project_id   uuid not null references projects (id) on delete cascade,
  release_date date,
  status       release_plan_status not null default 'draft',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz,
  unique (project_id)  -- one active plan per project (per ARCHITECTURE.md 2.5)
);
create index idx_release_plans_workspace on release_plans (workspace_id);

create table release_milestones (
  id              uuid primary key default gen_random_uuid(),
  release_plan_id uuid not null references release_plans (id) on delete cascade,
  title           text not null,
  category        milestone_category not null default 'marketing',
  due_date        date,
  status          milestone_status not null default 'pending',
  position        int not null default 0,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz
);
create index idx_milestones_plan on release_milestones (release_plan_id, position);

-- ===========================================================================
-- 2.6 Catalogue Vault
-- ===========================================================================
create table catalogue_items (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  project_id   uuid references projects (id) on delete set null,
  title        text not null,
  kind         catalogue_kind not null default 'track',
  status       catalogue_status not null default 'wip',
  isrc         text,
  bpm          int,
  key          text,
  storage_path text,
  file_size    bigint,
  tags         text[] not null default '{}',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_catalogue_workspace on catalogue_items (workspace_id);
create index idx_catalogue_project   on catalogue_items (project_id);
create index idx_catalogue_kind      on catalogue_items (workspace_id, kind);

-- ===========================================================================
-- 2.7 Budget Planner
-- ===========================================================================
create table budgets (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  project_id   uuid references projects (id) on delete set null,
  name         text not null,
  total_amount numeric(12,2),
  currency     text not null default 'NGN',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_budgets_workspace on budgets (workspace_id);

create table budget_items (
  id             uuid primary key default gen_random_uuid(),
  budget_id      uuid not null references budgets (id) on delete cascade,
  category       budget_category not null default 'other',
  label          text not null,
  planned_amount numeric(12,2),
  actual_amount  numeric(12,2),
  spent_at       date,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz
);
create index idx_budget_items_budget on budget_items (budget_id);

-- ===========================================================================
-- 2.8 Marketing Planner
-- ===========================================================================
create table campaigns (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  project_id   uuid references projects (id) on delete set null,
  name         text not null,
  objective    campaign_objective not null default 'awareness',
  status       campaign_status not null default 'planned',
  start_date   date,
  end_date     date,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_campaigns_workspace on campaigns (workspace_id);

create table content_pieces (
  id           uuid primary key default gen_random_uuid(),
  campaign_id  uuid not null references campaigns (id) on delete cascade,
  workspace_id uuid not null references workspaces (id) on delete cascade,
  platform     content_platform not null default 'other',
  format       content_format not null default 'post',
  scheduled_at timestamptz,
  status       content_status not null default 'idea',
  caption      text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_content_campaign  on content_pieces (campaign_id);
create index idx_content_workspace on content_pieces (workspace_id);

-- ===========================================================================
-- 2.10 Gravity Score (schema-ready)
-- ===========================================================================
create table gravity_scores (
  id                 uuid primary key default gen_random_uuid(),
  workspace_id       uuid not null references workspaces (id) on delete cascade,
  computed_at        timestamptz not null default now(),
  overall            int,
  consistency        int,
  organization       int,
  execution          int,
  marketing          int,
  collaboration      int,
  business_readiness int,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz
);
create index idx_gravity_scores_workspace on gravity_scores (workspace_id, computed_at desc);

-- ===========================================================================
-- 2.11 AI Manager (schema-ready)
-- ===========================================================================
create table ai_outputs (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces (id) on delete cascade,
  kind         ai_output_kind not null,
  payload      jsonb not null default '{}'::jsonb,
  generated_at timestamptz not null default now(),
  model        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);
create index idx_ai_outputs_workspace on ai_outputs (workspace_id, kind, generated_at desc);

-- ---------------------------------------------------------------------------
-- updated_at triggers for every table
-- ---------------------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array[
    'profiles','workspaces','workspace_members','projects','tasks',
    'calendar_events','release_plans','release_milestones','catalogue_items',
    'budgets','budget_items','campaigns','content_pieces','gravity_scores',
    'ai_outputs'
  ]
  loop
    execute format(
      'create trigger trg_%s_updated_at before update on %I
         for each row execute function set_updated_at();', t, t);
  end loop;
end;
$$;
