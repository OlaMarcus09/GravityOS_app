-- Deferred Enterprise foundations: multi-workspace organizations and
-- Soundcharts-backed streaming snapshots. No routes, jobs, or UI are enabled.

-- ---------------------------------------------------------------------------
-- Organizations
-- ---------------------------------------------------------------------------
create table public.organizations (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  owner_id   uuid not null references public.profiles (id) on delete restrict,
  plan       public.workspace_plan not null default 'enterprise',
  created_at timestamptz not null default now(),
  constraint organizations_enterprise_plan check (plan = 'enterprise')
);
create index idx_organizations_owner on public.organizations (owner_id);

create table public.organization_members (
  id         uuid primary key default gen_random_uuid(),
  org_id     uuid not null references public.organizations (id) on delete cascade,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  role       public.member_role not null default 'member',
  created_at timestamptz not null default now(),
  unique (org_id, user_id)
);
create index idx_organization_members_user on public.organization_members (user_id);
create index idx_organization_members_org on public.organization_members (org_id);

create table public.org_workspace_links (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null references public.organizations (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  linked_by    uuid not null references public.profiles (id) on delete restrict,
  created_at   timestamptz not null default now(),
  unique (org_id, workspace_id)
);
create index idx_org_workspace_links_workspace on public.org_workspace_links (workspace_id);
create index idx_org_workspace_links_org on public.org_workspace_links (org_id);

create or replace function private.is_org_member(org uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.organization_members m
    where m.org_id = org
      and m.user_id = auth.uid()
  );
$$;

create or replace function private.has_org_role(org uuid, roles public.member_role[])
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.organization_members m
    where m.org_id = org
      and m.user_id = auth.uid()
      and m.role = any (roles)
  );
$$;

create or replace function private.has_org_workspace_read(ws uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.org_workspace_links l
    where l.workspace_id = ws
      and private.is_org_member(l.org_id)
  );
$$;

create or replace function private.can_bootstrap_org_owner(org uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.organizations o
    where o.id = org
      and o.owner_id = auth.uid()
  )
  and not exists (
    select 1
    from public.organization_members m
    where m.org_id = org
  );
$$;

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.org_workspace_links enable row level security;

create policy organizations_select_member on public.organizations
  for select using (owner_id = auth.uid() or private.is_org_member(id));
create policy organizations_insert_owner on public.organizations
  for insert with check (owner_id = auth.uid() and plan = 'enterprise');
create policy organizations_update_owner on public.organizations
  for update using (owner_id = auth.uid())
  with check (owner_id = auth.uid() and plan = 'enterprise');
create policy organizations_delete_owner on public.organizations
  for delete using (owner_id = auth.uid());

create policy organization_members_select on public.organization_members
  for select using (private.is_org_member(org_id));
create policy organization_members_insert_bootstrap_owner on public.organization_members
  for insert with check (
    user_id = auth.uid()
    and role = 'owner'
    and private.can_bootstrap_org_owner(org_id)
  );
create policy organization_members_insert_manager on public.organization_members
  for insert with check (
    (
      private.has_org_role(org_id, array['owner']::public.member_role[])
      and role <> 'owner'
    )
    or (
      private.has_org_role(org_id, array['admin']::public.member_role[])
      and role = any (array['member','viewer']::public.member_role[])
    )
  );
create policy organization_members_update_manager on public.organization_members
  for update using (
    role <> 'owner'
    and private.has_org_role(org_id, array['owner','admin']::public.member_role[])
  )
  with check (
    role <> 'owner'
    and (
      private.has_org_role(org_id, array['owner']::public.member_role[])
      or (
        private.has_org_role(org_id, array['admin']::public.member_role[])
        and role = any (array['member','viewer']::public.member_role[])
      )
    )
  );
create policy organization_members_delete_manager on public.organization_members
  for delete using (
    role <> 'owner'
    and private.has_org_role(org_id, array['owner','admin']::public.member_role[])
  );

create policy org_workspace_links_select on public.org_workspace_links
  for select using (
    private.is_org_member(org_id)
    or private.is_workspace_member(workspace_id)
  );
create policy org_workspace_links_insert_workspace_owner on public.org_workspace_links
  for insert with check (
    linked_by = auth.uid()
    and private.has_workspace_role(
      workspace_id,
      array['owner']::public.member_role[]
    )
  );
create policy org_workspace_links_delete on public.org_workspace_links
  for delete using (
    private.has_workspace_role(workspace_id, array['owner']::public.member_role[])
    or private.has_org_role(org_id, array['owner','admin']::public.member_role[])
  );

-- Additive SELECT policies are ORed with the existing workspace-member
-- policies. Organization access remains read-only and limited to this list.
create policy workspaces_select_org_member on public.workspaces
  for select using (private.has_org_workspace_read(id));
create policy projects_select_org_member on public.projects
  for select using (private.has_org_workspace_read(workspace_id));
create policy tasks_select_org_member on public.tasks
  for select using (private.has_org_workspace_read(workspace_id));
create policy release_plans_select_org_member on public.release_plans
  for select using (private.has_org_workspace_read(workspace_id));
create policy budgets_select_org_member on public.budgets
  for select using (private.has_org_workspace_read(workspace_id));
create policy gravity_scores_select_org_member on public.gravity_scores
  for select using (private.has_org_workspace_read(workspace_id));

-- ---------------------------------------------------------------------------
-- Soundcharts identity links and service-owned metric snapshots
-- ---------------------------------------------------------------------------
create table public.artist_streaming_links (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references public.workspaces (id) on delete cascade,
  platform         text not null,
  soundcharts_uuid uuid not null,
  connected_at     timestamptz not null default now(),
  unique (workspace_id, platform),
  unique (id, workspace_id)
);
create index idx_artist_streaming_links_workspace
  on public.artist_streaming_links (workspace_id);

create table public.streaming_snapshots (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references public.workspaces (id) on delete cascade,
  artist_link_id uuid not null,
  captured_at    timestamptz not null default now(),
  platform       text not null,
  metric_type    text not null,
  value          numeric not null,
  constraint streaming_snapshots_artist_workspace_fk
    foreign key (artist_link_id, workspace_id)
    references public.artist_streaming_links (id, workspace_id)
    on delete cascade,
  unique (artist_link_id, captured_at, platform, metric_type)
);
create index idx_streaming_snapshots_workspace_captured
  on public.streaming_snapshots (workspace_id, captured_at desc);
create index idx_streaming_snapshots_metric_captured
  on public.streaming_snapshots (artist_link_id, platform, metric_type, captured_at desc);

drop trigger if exists trg_artist_streaming_links_workspace_immutable
  on public.artist_streaming_links;
create trigger trg_artist_streaming_links_workspace_immutable
before update of workspace_id on public.artist_streaming_links
for each row execute function public.prevent_workspace_reassignment();

alter table public.artist_streaming_links enable row level security;
alter table public.streaming_snapshots enable row level security;

-- Available to every workspace member on every plan. Plan gating is deferred.
create policy artist_streaming_links_select on public.artist_streaming_links
  for select using (private.is_workspace_member(workspace_id));
create policy artist_streaming_links_insert on public.artist_streaming_links
  for insert with check (private.is_workspace_writer(workspace_id));
create policy artist_streaming_links_update on public.artist_streaming_links
  for update using (private.is_workspace_writer(workspace_id))
  with check (private.is_workspace_writer(workspace_id));
create policy artist_streaming_links_delete on public.artist_streaming_links
  for delete using (private.is_workspace_writer(workspace_id));

-- Future polling writes use the service role. Members can read but cannot
-- forge, edit, or delete imported metrics.
create policy streaming_snapshots_select on public.streaming_snapshots
  for select using (private.is_workspace_member(workspace_id));
revoke insert, update, delete on public.streaming_snapshots from anon, authenticated;
