-- Record every manual workspace plan change as an immutable platform audit event.
create table if not exists public.admin_plan_audit_events (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references public.workspaces (id) on delete restrict,
  actor_id       uuid not null,
  actor_email    text not null,
  previous_plan  public.workspace_plan not null,
  new_plan       public.workspace_plan not null,
  created_at     timestamptz not null default now(),
  constraint admin_plan_audit_actual_change check (previous_plan <> new_plan)
);

create index if not exists idx_admin_plan_audit_workspace_created
  on public.admin_plan_audit_events (workspace_id, created_at desc);

alter table public.admin_plan_audit_events enable row level security;
revoke all on public.admin_plan_audit_events from anon, authenticated;

create or replace function private.prevent_admin_audit_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'admin audit events are immutable';
end;
$$;

drop trigger if exists admin_plan_audit_immutable on public.admin_plan_audit_events;
create trigger admin_plan_audit_immutable
before update or delete on public.admin_plan_audit_events
for each row execute function private.prevent_admin_audit_mutation();

create or replace function public.admin_set_workspace_plan(
  p_workspace_id uuid,
  p_new_plan public.workspace_plan,
  p_actor_id uuid,
  p_actor_email text
)
returns public.workspaces
language plpgsql
security definer
set search_path = public, private
as $$
declare
  previous public.workspace_plan;
  changed public.workspaces;
begin
  select plan into previous
  from public.workspaces
  where id = p_workspace_id
  for update;

  if not found then
    raise exception 'workspace not found' using errcode = 'P0002';
  end if;

  if previous = p_new_plan then
    return (select w from public.workspaces w where w.id = p_workspace_id);
  end if;

  update public.workspaces
  set plan = p_new_plan,
      updated_at = now()
  where id = p_workspace_id
  returning * into changed;

  insert into public.admin_plan_audit_events (
    workspace_id, actor_id, actor_email, previous_plan, new_plan
  ) values (
    p_workspace_id, p_actor_id, lower(p_actor_email), previous, p_new_plan
  );

  return changed;
end;
$$;

revoke all on function public.admin_set_workspace_plan(uuid, public.workspace_plan, uuid, text)
  from public, anon, authenticated;
grant execute on function public.admin_set_workspace_plan(uuid, public.workspace_plan, uuid, text)
  to service_role;

create table if not exists public.admin_account_audit_events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,
  user_email  text not null,
  actor_id    uuid not null,
  actor_email text not null,
  action      text not null check (action in ('suspend', 'reactivate')),
  created_at  timestamptz not null default now()
);

create index if not exists idx_admin_account_audit_created
  on public.admin_account_audit_events (created_at desc);

alter table public.admin_account_audit_events enable row level security;
revoke all on public.admin_account_audit_events from anon, authenticated;

drop trigger if exists admin_account_audit_immutable on public.admin_account_audit_events;
create trigger admin_account_audit_immutable
before update or delete on public.admin_account_audit_events
for each row execute function private.prevent_admin_audit_mutation();
