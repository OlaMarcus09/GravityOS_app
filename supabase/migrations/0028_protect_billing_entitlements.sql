-- Keep workspace creation and administrator grants within the billing trust boundary.

create or replace function private.prevent_client_workspace_billing_insert()
returns trigger
language plpgsql
set search_path = public, private
as $$
begin
  if auth.uid() is not null and (
    new.plan <> 'free'
    or new.billing_status <> 'none'
    or new.current_period_start is not null
    or new.current_period_end is not null
    or new.last_billing_transaction_id is not null
  ) then
    raise exception 'workspace billing entitlements require the admin service'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger prevent_client_workspace_billing_insert
before insert on public.workspaces
for each row execute function private.prevent_client_workspace_billing_insert();

-- A plan granted by a platform administrator has no Flutterwave entitlement.
-- Clear old payment dates when a grant replaces or removes a paid plan.
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
      billing_status = case when p_new_plan = 'free' then 'none'::public.workspace_billing_status
                            else 'manual'::public.workspace_billing_status end,
      current_period_start = null,
      current_period_end = null,
      last_billing_transaction_id = null,
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

-- Repair any paid plan granted after 0026 but before this migration.
update public.workspaces
set billing_status = 'manual'
where plan in ('pro', 'team', 'enterprise') and billing_status = 'none';
