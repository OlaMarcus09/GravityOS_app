-- Enforce plan-gated writes at the database boundary.
-- FastAPI checks are useful for friendly errors, but authenticated clients can
-- also call Supabase directly, so RLS/triggers must enforce the same rules.

create or replace function private.is_paid_workspace(ws uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1
    from public.workspaces w
    where w.id = ws
      and w.plan in ('pro', 'team', 'enterprise')
  );
$$;

-- A client must not be able to mint a paid workspace, upgrade itself, or
-- transfer ownership by writing workspaces directly. Plan changes go through
-- the service-role admin RPC, which also records the immutable audit event.
drop policy if exists workspaces_insert_authed on public.workspaces;
create policy workspaces_insert_authed on public.workspaces
  for insert with check (owner_id = auth.uid() and plan = 'free');

create or replace function private.prevent_client_plan_change()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
begin
  if auth.uid() is not null and (
    new.plan is distinct from old.plan
    or new.owner_id is distinct from old.owner_id
  ) then
    raise exception 'workspace plan or ownership changes require the admin service'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

drop trigger if exists prevent_client_plan_change on public.workspaces;
create trigger prevent_client_plan_change
before update of plan on public.workspaces
for each row execute function private.prevent_client_plan_change();

-- Free workspaces may keep archived projects, but may have only one active
-- project. This trigger covers both direct inserts and status transitions,
-- including calls made through the Supabase REST API.
create or replace function private.enforce_free_project_limit()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
declare
  active_count integer;
begin
  -- Service-role jobs and trusted migrations are not subject to tenant plan
  -- limits. auth.uid() is null for those calls.
  if auth.uid() is null or new.status = 'archived' then
    return new;
  end if;

  -- Changing one active status to another does not consume another slot.
  if tg_op = 'UPDATE'
     and old.workspace_id = new.workspace_id
     and old.status <> 'archived' then
    return new;
  end if;

  if exists (
    select 1 from public.workspaces w
    where w.id = new.workspace_id and w.plan = 'free'
  ) then
    -- Serialize concurrent creates/status changes in the same workspace so
    -- two requests cannot both observe a count below the limit.
    perform pg_advisory_xact_lock(hashtextextended(new.workspace_id::text, 0));

    select count(*) into active_count
    from public.projects p
    where p.workspace_id = new.workspace_id
      and p.status <> 'archived'
      and (tg_op <> 'UPDATE' or p.id <> new.id);

    if active_count >= 1 then
      raise exception 'free plan allows 1 active project' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists enforce_free_project_limit on public.projects;
create trigger enforce_free_project_limit
before insert or update of workspace_id, status on public.projects
for each row execute function private.enforce_free_project_limit();

-- The Free catalogue allowance is 25 items. As with projects, an advisory
-- transaction lock makes the count-and-insert decision concurrency-safe.
create or replace function private.enforce_free_catalogue_limit()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
declare
  item_count integer;
begin
  if auth.uid() is null then
    return new;
  end if;

  if exists (
    select 1 from public.workspaces w
    where w.id = new.workspace_id and w.plan = 'free'
  ) then
    perform pg_advisory_xact_lock(hashtextextended(new.workspace_id::text, 1));

    select count(*) into item_count
    from public.catalogue_items c
    where c.workspace_id = new.workspace_id
      and (tg_op <> 'UPDATE' or c.id <> new.id);

    if item_count >= 25 then
      raise exception 'free plan allows 25 catalogue items' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists enforce_free_catalogue_limit on public.catalogue_items;
create trigger enforce_free_catalogue_limit
before insert or update of workspace_id on public.catalogue_items
for each row execute function private.enforce_free_catalogue_limit();

-- Pro/Team/Enterprise-only tables. Reads remain available to all workspace
-- members; only write paths are restricted here.
drop policy if exists release_plans_insert on public.release_plans;
create policy release_plans_insert on public.release_plans
  for insert with check (
    private.is_workspace_writer(workspace_id)
    and private.is_paid_workspace(workspace_id)
  );
drop policy if exists release_plans_update on public.release_plans;
create policy release_plans_update on public.release_plans
  for update using (
    private.is_workspace_writer(workspace_id)
    and private.is_paid_workspace(workspace_id)
  ) with check (
    private.is_workspace_writer(workspace_id)
    and private.is_paid_workspace(workspace_id)
  );
drop policy if exists release_plans_delete on public.release_plans;
create policy release_plans_delete on public.release_plans
  for delete using (
    private.is_workspace_writer(workspace_id)
    and private.is_paid_workspace(workspace_id)
  );

drop policy if exists milestones_insert on public.release_milestones;
create policy milestones_insert on public.release_milestones
  for insert with check (exists (
    select 1 from public.release_plans p
    where p.id = release_plan_id
      and private.is_workspace_writer(p.workspace_id)
      and private.is_paid_workspace(p.workspace_id)
  ));
drop policy if exists milestones_update on public.release_milestones;
create policy milestones_update on public.release_milestones
  for update using (exists (
    select 1 from public.release_plans p
    where p.id = release_plan_id
      and private.is_workspace_writer(p.workspace_id)
      and private.is_paid_workspace(p.workspace_id)
  )) with check (exists (
    select 1 from public.release_plans p
    where p.id = release_plan_id
      and private.is_workspace_writer(p.workspace_id)
      and private.is_paid_workspace(p.workspace_id)
  ));
drop policy if exists milestones_delete on public.release_milestones;
create policy milestones_delete on public.release_milestones
  for delete using (exists (
    select 1 from public.release_plans p
    where p.id = release_plan_id
      and private.is_workspace_writer(p.workspace_id)
      and private.is_paid_workspace(p.workspace_id)
  ));

drop policy if exists budgets_insert on public.budgets;
create policy budgets_insert on public.budgets
  for insert with check (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));
drop policy if exists budgets_update on public.budgets;
create policy budgets_update on public.budgets
  for update using (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id))
  with check (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));
drop policy if exists budgets_delete on public.budgets;
create policy budgets_delete on public.budgets
  for delete using (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));

drop policy if exists budget_items_insert on public.budget_items;
create policy budget_items_insert on public.budget_items
  for insert with check (exists (select 1 from public.budgets b where b.id = budget_id and private.is_workspace_writer(b.workspace_id) and private.is_paid_workspace(b.workspace_id)));
drop policy if exists budget_items_update on public.budget_items;
create policy budget_items_update on public.budget_items
  for update using (exists (select 1 from public.budgets b where b.id = budget_id and private.is_workspace_writer(b.workspace_id) and private.is_paid_workspace(b.workspace_id)))
  with check (exists (select 1 from public.budgets b where b.id = budget_id and private.is_workspace_writer(b.workspace_id) and private.is_paid_workspace(b.workspace_id)));
drop policy if exists budget_items_delete on public.budget_items;
create policy budget_items_delete on public.budget_items
  for delete using (exists (select 1 from public.budgets b where b.id = budget_id and private.is_workspace_writer(b.workspace_id) and private.is_paid_workspace(b.workspace_id)));

drop policy if exists campaigns_insert on public.campaigns;
create policy campaigns_insert on public.campaigns
  for insert with check (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));
drop policy if exists campaigns_update on public.campaigns;
create policy campaigns_update on public.campaigns
  for update using (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id))
  with check (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));
drop policy if exists campaigns_delete on public.campaigns;
create policy campaigns_delete on public.campaigns
  for delete using (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));

drop policy if exists content_insert on public.content_pieces;
create policy content_insert on public.content_pieces
  for insert with check (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));
drop policy if exists content_update on public.content_pieces;
create policy content_update on public.content_pieces
  for update using (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id))
  with check (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));
drop policy if exists content_delete on public.content_pieces;
create policy content_delete on public.content_pieces
  for delete using (private.is_workspace_writer(workspace_id) and private.is_paid_workspace(workspace_id));

revoke all on function private.is_paid_workspace(uuid) from public;
grant execute on function private.is_paid_workspace(uuid) to authenticated, service_role;
revoke all on function private.prevent_client_plan_change() from public;
revoke all on function private.enforce_free_project_limit() from public;
revoke all on function private.enforce_free_catalogue_limit() from public;
