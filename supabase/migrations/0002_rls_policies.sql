-- Gravity OS — Row Level Security
-- Per ARCHITECTURE.md section 2: a tenant row is visible only if the
-- requesting user is a member of its workspace. RLS is the backstop that
-- keeps a leaked/misused token from crossing workspace boundaries even
-- though FastAPI also enforces membership (ARCHITECTURE.md section 1).
--
-- auth.uid() returns the authenticated user's id (= profiles.id).

-- ---------------------------------------------------------------------------
-- Helper: is the current user a member of the given workspace?
-- SECURITY DEFINER so the membership lookup itself isn't gated by RLS
-- (avoids infinite recursion on workspace_members policies).
-- ---------------------------------------------------------------------------
create or replace function is_workspace_member(ws uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1
    from workspace_members m
    where m.workspace_id = ws
      and m.user_id = auth.uid()
  );
$$;

create or replace function has_workspace_role(ws uuid, roles member_role[])
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1
    from workspace_members m
    where m.workspace_id = ws
      and m.user_id = auth.uid()
      and m.role = any (roles)
  );
$$;

-- Writer = any role that may mutate tenant data. Viewers are read-only, so
-- write policies gate on this rather than plain membership. This makes RLS
-- (not just FastAPI's require_writer) the real backstop for viewer read-only,
-- since the browser can call Supabase directly per ARCHITECTURE.md.
create or replace function is_workspace_writer(ws uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select has_workspace_role(ws, array['owner','admin','member']::member_role[]);
$$;

-- ---------------------------------------------------------------------------
-- Enable RLS on every table
-- ---------------------------------------------------------------------------
alter table profiles          enable row level security;
alter table workspaces        enable row level security;
alter table workspace_members enable row level security;
alter table projects          enable row level security;
alter table tasks             enable row level security;
alter table calendar_events   enable row level security;
alter table release_plans     enable row level security;
alter table release_milestones enable row level security;
alter table catalogue_items   enable row level security;
alter table budgets           enable row level security;
alter table budget_items      enable row level security;
alter table campaigns         enable row level security;
alter table content_pieces    enable row level security;
alter table gravity_scores    enable row level security;
alter table ai_outputs        enable row level security;

-- ===========================================================================
-- profiles: a user can see/edit their own profile. (Team-member profile
-- visibility can be widened later; kept tight for MVP.)
-- ===========================================================================
create policy profiles_select_own on profiles
  for select using (id = auth.uid());
create policy profiles_update_own on profiles
  for update using (id = auth.uid()) with check (id = auth.uid());
create policy profiles_insert_own on profiles
  for insert with check (id = auth.uid());

-- ===========================================================================
-- workspaces: members can read; only owner/admin can update; any authed
-- user can create a workspace (they become owner via the members insert).
-- ===========================================================================
create policy workspaces_select_member on workspaces
  for select using (is_workspace_member(id));
create policy workspaces_insert_authed on workspaces
  for insert with check (owner_id = auth.uid());
create policy workspaces_update_admin on workspaces
  for update using (has_workspace_role(id, array['owner','admin']::member_role[]))
  with check (has_workspace_role(id, array['owner','admin']::member_role[]));
create policy workspaces_delete_owner on workspaces
  for delete using (has_workspace_role(id, array['owner']::member_role[]));

-- ===========================================================================
-- workspace_members: members can see the roster; owner/admin manage it.
-- Insert is split into two intents so self-insertion can't be abused:
--   1. Bootstrap: the workspace creator adds themselves as owner, but only
--      for a workspace they own AND only while it has no members yet. This
--      closes the privilege-escalation hole where any authed user could
--      insert themselves as owner of any workspace by UUID.
--   2. Invites: an existing owner/admin may add anyone with any role.
-- ===========================================================================
create policy members_select on workspace_members
  for select using (is_workspace_member(workspace_id));
create policy members_insert_bootstrap_owner on workspace_members
  for insert with check (
    user_id = auth.uid()
    and role = 'owner'
    and exists (
      select 1 from workspaces w
      where w.id = workspace_id
        and w.owner_id = auth.uid()
    )
    and not exists (
      select 1 from workspace_members m2
      where m2.workspace_id = workspace_id
    )
  );
create policy members_insert_admin on workspace_members
  for insert with check (
    has_workspace_role(workspace_id, array['owner','admin']::member_role[])
  );
create policy members_update_admin on workspace_members
  for update using (has_workspace_role(workspace_id, array['owner','admin']::member_role[]))
  with check (has_workspace_role(workspace_id, array['owner','admin']::member_role[]));
create policy members_delete_admin on workspace_members
  for delete using (has_workspace_role(workspace_id, array['owner','admin']::member_role[]));

-- ===========================================================================
-- Generic tenant tables: any member may read; only writers (owner/admin/
-- member) may mutate. Select and write are separate policies so the viewer
-- read-only rule is enforced by RLS itself, not only by FastAPI — the browser
-- can hit Supabase directly per ARCHITECTURE.md, so RLS must be the backstop.
-- Child tables (release_milestones, budget_items) derive workspace via parent.
-- ===========================================================================

-- projects
create policy projects_select on projects
  for select using (is_workspace_member(workspace_id));
create policy projects_insert on projects
  for insert with check (is_workspace_writer(workspace_id));
create policy projects_update on projects
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy projects_delete on projects
  for delete using (is_workspace_writer(workspace_id));

-- tasks
create policy tasks_select on tasks
  for select using (is_workspace_member(workspace_id));
create policy tasks_insert on tasks
  for insert with check (is_workspace_writer(workspace_id));
create policy tasks_update on tasks
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy tasks_delete on tasks
  for delete using (is_workspace_writer(workspace_id));

-- calendar_events
create policy calendar_select on calendar_events
  for select using (is_workspace_member(workspace_id));
create policy calendar_insert on calendar_events
  for insert with check (is_workspace_writer(workspace_id));
create policy calendar_update on calendar_events
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy calendar_delete on calendar_events
  for delete using (is_workspace_writer(workspace_id));

-- release_plans
create policy release_plans_select on release_plans
  for select using (is_workspace_member(workspace_id));
create policy release_plans_insert on release_plans
  for insert with check (is_workspace_writer(workspace_id));
create policy release_plans_update on release_plans
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy release_plans_delete on release_plans
  for delete using (is_workspace_writer(workspace_id));

-- release_milestones: scoped via parent plan's workspace
create policy milestones_select on release_milestones
  for select using (
    exists (
      select 1 from release_plans p
      where p.id = release_plan_id
        and is_workspace_member(p.workspace_id)
    )
  );
create policy milestones_insert on release_milestones
  for insert with check (
    exists (
      select 1 from release_plans p
      where p.id = release_plan_id
        and is_workspace_writer(p.workspace_id)
    )
  );
create policy milestones_update on release_milestones
  for update using (
    exists (
      select 1 from release_plans p
      where p.id = release_plan_id
        and is_workspace_writer(p.workspace_id)
    )
  )
  with check (
    exists (
      select 1 from release_plans p
      where p.id = release_plan_id
        and is_workspace_writer(p.workspace_id)
    )
  );
create policy milestones_delete on release_milestones
  for delete using (
    exists (
      select 1 from release_plans p
      where p.id = release_plan_id
        and is_workspace_writer(p.workspace_id)
    )
  );

-- catalogue_items
create policy catalogue_select on catalogue_items
  for select using (is_workspace_member(workspace_id));
create policy catalogue_insert on catalogue_items
  for insert with check (is_workspace_writer(workspace_id));
create policy catalogue_update on catalogue_items
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy catalogue_delete on catalogue_items
  for delete using (is_workspace_writer(workspace_id));

-- budgets
create policy budgets_select on budgets
  for select using (is_workspace_member(workspace_id));
create policy budgets_insert on budgets
  for insert with check (is_workspace_writer(workspace_id));
create policy budgets_update on budgets
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy budgets_delete on budgets
  for delete using (is_workspace_writer(workspace_id));

-- budget_items: scoped via parent budget's workspace
create policy budget_items_select on budget_items
  for select using (
    exists (
      select 1 from budgets b
      where b.id = budget_id
        and is_workspace_member(b.workspace_id)
    )
  );
create policy budget_items_insert on budget_items
  for insert with check (
    exists (
      select 1 from budgets b
      where b.id = budget_id
        and is_workspace_writer(b.workspace_id)
    )
  );
create policy budget_items_update on budget_items
  for update using (
    exists (
      select 1 from budgets b
      where b.id = budget_id
        and is_workspace_writer(b.workspace_id)
    )
  )
  with check (
    exists (
      select 1 from budgets b
      where b.id = budget_id
        and is_workspace_writer(b.workspace_id)
    )
  );
create policy budget_items_delete on budget_items
  for delete using (
    exists (
      select 1 from budgets b
      where b.id = budget_id
        and is_workspace_writer(b.workspace_id)
    )
  );

-- campaigns
create policy campaigns_select on campaigns
  for select using (is_workspace_member(workspace_id));
create policy campaigns_insert on campaigns
  for insert with check (is_workspace_writer(workspace_id));
create policy campaigns_update on campaigns
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy campaigns_delete on campaigns
  for delete using (is_workspace_writer(workspace_id));

-- content_pieces
create policy content_select on content_pieces
  for select using (is_workspace_member(workspace_id));
create policy content_insert on content_pieces
  for insert with check (is_workspace_writer(workspace_id));
create policy content_update on content_pieces
  for update using (is_workspace_writer(workspace_id))
  with check (is_workspace_writer(workspace_id));
create policy content_delete on content_pieces
  for delete using (is_workspace_writer(workspace_id));

-- gravity_scores (read-only for members in MVP; written by service role)
create policy gravity_select on gravity_scores
  for select using (is_workspace_member(workspace_id));

-- ai_outputs (read-only for members in MVP; written by service role)
create policy ai_outputs_select on ai_outputs
  for select using (is_workspace_member(workspace_id));
