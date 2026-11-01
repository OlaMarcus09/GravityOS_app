-- Seven full days of Pro for one new workspace per verified identity.
-- The campaign is disabled until an explicit deployment step enables it.
-- Existing workspaces and billing records are not changed by this migration.

alter table public.workspaces
  add column trial_started_at timestamptz,
  add column trial_expires_at timestamptz,
  add constraint workspaces_trial_period_exact
    check (
      (trial_started_at is null and trial_expires_at is null)
      or (trial_started_at is not null and trial_expires_at = trial_started_at + interval '168 hours')
    );

create table private.founder_trial_campaign (
  singleton boolean primary key default true check (singleton),
  enabled boolean not null default false,
  enrollment_starts_at timestamptz,
  enrollment_ends_at timestamptz,
  constraint founder_trial_campaign_window check (
    enrollment_starts_at is null or enrollment_ends_at is null
    or enrollment_ends_at > enrollment_starts_at
  )
);
insert into private.founder_trial_campaign (singleton, enabled) values (true, false);
revoke all on private.founder_trial_campaign from public, anon, authenticated;

-- Keep claims even if a workspace or account is later deleted. The email
-- digest catches recreation under the same address; distinct identities are
-- outside the reach of a card-free promotion.
create table private.founder_trial_claims (
  owner_id uuid primary key,
  email_digest bytea not null unique,
  workspace_id uuid not null unique,
  claimed_at timestamptz not null
);
revoke all on private.founder_trial_claims from public, anon, authenticated;

create or replace function private.prevent_client_trial_change()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
begin
  if auth.uid() is not null and (
    (tg_op = 'INSERT' and (new.trial_started_at is not null or new.trial_expires_at is not null))
    or (tg_op = 'UPDATE' and (
      new.trial_started_at is distinct from old.trial_started_at
      or new.trial_expires_at is distinct from old.trial_expires_at
    ))
  ) then
    raise exception 'trial entitlements require the admin service' using errcode = '42501';
  end if;
  return new;
end;
$$;
create trigger prevent_client_trial_change
before insert or update of trial_started_at, trial_expires_at on public.workspaces
for each row execute function private.prevent_client_trial_change();
revoke all on function private.prevent_client_trial_change() from public;

-- BEFORE triggers fire in name order. This runs after the client entitlement
-- guards, and leaves the stored plan Free. The unique claim makes concurrent
-- workspace creation by the same owner/email award at most one trial.
create or replace function private.zz_claim_founder_trial()
returns trigger
language plpgsql
security definer
set search_path = public, private, auth
as $$
declare
  v_email text;
  v_user_created_at timestamptz;
  v_claimed uuid;
  v_now timestamptz := clock_timestamp();
begin
  if new.plan <> 'free' or new.billing_status <> 'none'
     or new.trial_started_at is not null or new.trial_expires_at is not null then
    return new;
  end if;

  if not exists (
    select 1 from private.founder_trial_campaign c
    where c.singleton and c.enabled
      and c.enrollment_starts_at <= v_now
      and c.enrollment_ends_at > v_now
  ) then
    return new;
  end if;

  select lower(btrim(u.email)), u.created_at into v_email, v_user_created_at
  from auth.users u where u.id = new.owner_id and u.email_confirmed_at is not null;
  if v_email is null or v_email = '' then
    return new;
  end if;
  if v_user_created_at < (select c.enrollment_starts_at from private.founder_trial_campaign c where c.singleton) then
    return new;
  end if;

  insert into private.founder_trial_claims (owner_id, email_digest, workspace_id, claimed_at)
  values (new.owner_id, digest(v_email, 'sha256'), new.id, v_now)
  on conflict do nothing
  returning owner_id into v_claimed;
  if v_claimed is not null then
    new.trial_started_at := v_now;
    new.trial_expires_at := v_now + interval '168 hours';
  end if;
  return new;
end;
$$;
create trigger zz_claim_founder_trial
before insert on public.workspaces
for each row execute function private.zz_claim_founder_trial();
revoke all on function private.zz_claim_founder_trial() from public;

-- Email-confirmation projects create the default workspace before the email
-- is confirmed. Start its full 168-hour period only when confirmation lands.
create or replace function private.claim_founder_trial_on_confirmation()
returns trigger
language plpgsql
security definer
set search_path = public, private, auth
as $$
declare
  v_workspace_id uuid;
  v_claimed uuid;
  v_now timestamptz := clock_timestamp();
begin
  if old.email_confirmed_at is not null or new.email_confirmed_at is null then
    return new;
  end if;
  if new.created_at < (select c.enrollment_starts_at from private.founder_trial_campaign c where c.singleton) then
    return new;
  end if;
  if not exists (
    select 1 from private.founder_trial_campaign c
    where c.singleton and c.enabled
      and c.enrollment_starts_at <= v_now and c.enrollment_ends_at > v_now
  ) then
    return new;
  end if;
  select w.id into v_workspace_id from public.workspaces w
  where w.owner_id = new.id and w.plan = 'free' and w.billing_status = 'none'
    and w.trial_started_at is null and w.trial_expires_at is null
  order by w.created_at, w.id limit 1 for update;
  if v_workspace_id is null then return new; end if;
  insert into private.founder_trial_claims (owner_id, email_digest, workspace_id, claimed_at)
  values (new.id, digest(lower(btrim(new.email)), 'sha256'), v_workspace_id, v_now)
  on conflict do nothing returning owner_id into v_claimed;
  if v_claimed is not null then
    update public.workspaces
    set trial_started_at = v_now, trial_expires_at = v_now + interval '168 hours'
    where id = v_workspace_id;
  end if;
  return new;
end;
$$;
create trigger claim_founder_trial_on_confirmation
after update of email_confirmed_at on auth.users
for each row execute function private.claim_founder_trial_on_confirmation();
revoke all on function private.claim_founder_trial_on_confirmation() from public;

-- All RLS paid-feature writes and Free limits use this clock-based result.
-- A transaction started before expiry cannot keep its trial entitlement after
-- the deadline; each authorization evaluates the current wall clock.
create or replace function private.workspace_effective_plan(ws uuid)
returns public.workspace_plan
language sql
security definer
set search_path = public, private
volatile
as $$
  select case
    when w.billing_status = 'manual' and w.plan in ('pro', 'team', 'enterprise') then w.plan
    when w.billing_status = 'active' and w.plan in ('pro', 'team')
      and w.current_period_end > clock_timestamp() then w.plan
    when w.plan = 'free' and w.billing_status = 'none'
      and w.trial_started_at <= clock_timestamp()
      and w.trial_expires_at > clock_timestamp() then 'pro'::public.workspace_plan
    else 'free'::public.workspace_plan
  end
  from public.workspaces w where w.id = ws;
$$;
revoke all on function private.workspace_effective_plan(uuid) from public;
grant execute on function private.workspace_effective_plan(uuid) to authenticated, service_role;

create or replace function private.is_paid_workspace(ws uuid)
returns boolean
language sql
security definer
set search_path = public, private
volatile
as $$
  select coalesce(private.workspace_effective_plan(ws) <> 'free', false);
$$;
revoke all on function private.is_paid_workspace(uuid) from public;
grant execute on function private.is_paid_workspace(uuid) to authenticated, service_role;

create or replace function private.enforce_free_project_limit()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
declare
  active_count integer;
begin
  if auth.uid() is null or new.status = 'archived' then return new; end if;
  if tg_op = 'UPDATE' and old.workspace_id = new.workspace_id and old.status <> 'archived' then
    return new;
  end if;
  if private.workspace_effective_plan(new.workspace_id) = 'free' then
    perform pg_advisory_xact_lock(hashtextextended(new.workspace_id::text, 0));
    select count(*) into active_count from public.projects p
    where p.workspace_id = new.workspace_id and p.status <> 'archived'
      and (tg_op <> 'UPDATE' or p.id <> new.id);
    if active_count >= 1 then
      raise exception 'free plan allows 1 active project' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;

create or replace function private.enforce_free_catalogue_limit()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
declare
  item_count integer;
begin
  if auth.uid() is null then return new; end if;
  if private.workspace_effective_plan(new.workspace_id) = 'free' then
    perform pg_advisory_xact_lock(hashtextextended(new.workspace_id::text, 1));
    select count(*) into item_count from public.catalogue_items c
    where c.workspace_id = new.workspace_id and (tg_op <> 'UPDATE' or c.id <> new.id);
    if item_count >= 25 then
      raise exception 'free plan allows 25 catalogue items' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;

-- An administrator's explicit plan decision ends a trial. The claim remains
-- consumed, so setting Free later cannot grant another seven days.
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
  select plan into previous from public.workspaces where id = p_workspace_id for update;
  if not found then raise exception 'workspace not found' using errcode = 'P0002'; end if;
  if previous = p_new_plan and not exists (
    select 1 from public.workspaces w where w.id = p_workspace_id and w.trial_expires_at is not null
  ) then
    return (select w from public.workspaces w where w.id = p_workspace_id);
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
    (workspace_id, actor_id, actor_email, previous_plan, new_plan)
  values (p_workspace_id, p_actor_id, lower(p_actor_email), previous, p_new_plan);
  return changed;
end;
$$;
revoke all on function public.admin_set_workspace_plan(uuid, public.workspace_plan, uuid, text)
  from public, anon, authenticated;
grant execute on function public.admin_set_workspace_plan(uuid, public.workspace_plan, uuid, text)
  to service_role;
