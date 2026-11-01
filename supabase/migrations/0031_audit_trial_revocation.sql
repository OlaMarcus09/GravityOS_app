-- Revoking a trial changes the entitlement while the stored plan stays Free.
-- Preserve that change in the immutable audit instead of attempting an invalid
-- Free-to-Free plan-only event. Existing plan grants and audit rows are unchanged.

alter table public.admin_plan_audit_events
  add column previous_trial_expires_at timestamptz,
  drop constraint admin_plan_audit_actual_change,
  add constraint admin_plan_audit_actual_change
    check (previous_plan <> new_plan or previous_trial_expires_at is not null);

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
  previous public.workspaces;
  changed public.workspaces;
begin
  select * into previous from public.workspaces where id = p_workspace_id for update;
  if not found then raise exception 'workspace not found' using errcode = 'P0002'; end if;
  if previous.plan = p_new_plan and previous.trial_expires_at is null then
    return previous;
  end if;

  update public.workspaces
  set plan = p_new_plan,
      billing_status = case when p_new_plan = 'free' then 'none'::public.workspace_billing_status
                            else 'manual'::public.workspace_billing_status end,
      current_period_start = null, current_period_end = null,
      last_billing_transaction_id = null,
      trial_started_at = null, trial_expires_at = null,
      updated_at = now()
  where id = p_workspace_id returning * into changed;

  insert into public.admin_plan_audit_events
    (workspace_id, actor_id, actor_email, previous_plan, new_plan, previous_trial_expires_at)
  values (p_workspace_id, p_actor_id, lower(p_actor_email), previous.plan, p_new_plan,
          previous.trial_expires_at);
  return changed;
end;
$$;

revoke all on function public.admin_set_workspace_plan(uuid, public.workspace_plan, uuid, text)
  from public, anon, authenticated;
grant execute on function public.admin_set_workspace_plan(uuid, public.workspace_plan, uuid, text)
  to service_role;
