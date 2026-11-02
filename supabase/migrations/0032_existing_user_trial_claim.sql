-- A separate, disabled offer for accounts that predate the public trial.
-- Store the founder's exact 23:59:59 WAT deadline as 22:59:59 UTC.
-- The comparison includes every microsecond of that final second.
create table private.existing_user_trial_campaign (
  singleton boolean primary key default true check (singleton),
  enabled boolean not null default false,
  starts_at timestamptz,
  ends_at timestamptz not null default '2026-11-15 22:59:59+00',
  account_created_before timestamptz not null default '2026-11-01 12:49:03.416065+00',
  constraint existing_user_trial_window check (starts_at is null or ends_at > starts_at)
);
insert into private.existing_user_trial_campaign (singleton) values (true);
revoke all on private.existing_user_trial_campaign from public, anon, authenticated;

-- This helper is deliberately inaccessible through the Data API. Every
-- response describes only the caller and the selected workspace.
create function private.existing_user_trial_status(p_owner_id uuid, p_workspace_id uuid, p_at timestamptz)
returns text
language plpgsql security definer set search_path = ''
as $$
declare
  v_user auth.users%rowtype;
  v_workspace public.workspaces%rowtype;
  v_campaign private.existing_user_trial_campaign%rowtype;
begin
  select * into v_workspace from public.workspaces where id = p_workspace_id;
  if not found or v_workspace.owner_id <> p_owner_id or not exists (
    select 1 from public.workspace_members m
    where m.workspace_id = p_workspace_id and m.user_id = p_owner_id and m.role = 'owner'
  ) then return 'not_owner'; end if;

  select * into v_user from auth.users where id = p_owner_id;
  if not found then return 'not_owner'; end if;
  select * into v_campaign from private.existing_user_trial_campaign where singleton;
  if not found then return 'window_closed'; end if;

  if v_user.email_confirmed_at is null then return 'email_confirmation_required'; end if;
  if v_user.created_at >= v_campaign.account_created_before then return 'not_eligible'; end if;
  if v_user.email is null or pg_catalog.btrim(v_user.email) = '' then return 'not_eligible'; end if;
  if exists (
    select 1 from private.founder_trial_claims c
    where c.owner_id = p_owner_id
       or c.email_digest = extensions.digest(pg_catalog.lower(pg_catalog.btrim(v_user.email)), 'sha256')
  ) then return 'already_claimed'; end if;

  if exists (
    select 1 from public.workspaces w where w.owner_id = p_owner_id
      and ((w.billing_status = 'manual' and w.plan in ('pro', 'team', 'enterprise'))
       or (w.billing_status = 'active' and w.plan in ('pro', 'team') and w.current_period_end > p_at))
  ) then return 'paid_workspace_conflict'; end if;
  if v_workspace.plan <> 'free' or v_workspace.billing_status <> 'none'
     or v_workspace.trial_started_at is not null or v_workspace.trial_expires_at is not null
  then return 'not_eligible'; end if;
  if not v_campaign.enabled or v_campaign.starts_at is null
     or p_at < v_campaign.starts_at or p_at >= v_campaign.ends_at + interval '1 second'
  then return 'window_closed'; end if;
  return 'eligible';
end;
$$;
revoke all on function private.existing_user_trial_status(uuid, uuid, timestamptz) from public, anon, authenticated;

create function public.existing_user_trial_eligibility(p_owner_id uuid, p_workspace_id uuid)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_status text;
begin
  v_status := private.existing_user_trial_status(p_owner_id, p_workspace_id, pg_catalog.clock_timestamp());
  return pg_catalog.jsonb_build_object('eligible', v_status = 'eligible', 'reason', v_status);
end;
$$;
revoke all on function public.existing_user_trial_eligibility(uuid, uuid) from public, anon, authenticated;
grant execute on function public.existing_user_trial_eligibility(uuid, uuid) to service_role;

create function public.claim_existing_user_trial(p_owner_id uuid, p_workspace_id uuid)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_status text;
  v_now timestamptz;
  v_email text;
  v_claimed uuid;
begin
  -- Serializes claims by this identity; the ledger's unique owner/email and
  -- workspace keys protect retries and alternate workspaces as well.
  perform 1 from auth.users where id = p_owner_id for update;
  if not found then return pg_catalog.jsonb_build_object('reason', 'not_owner'); end if;
  perform 1 from public.workspaces where id = p_workspace_id for update;
  -- Lock every existing owned workspace before checking paid entitlements.
  perform 1 from public.workspaces where owner_id = p_owner_id order by id for update;
  v_now := pg_catalog.clock_timestamp();
  v_status := private.existing_user_trial_status(p_owner_id, p_workspace_id, v_now);
  if v_status <> 'eligible' then
    return pg_catalog.jsonb_build_object('reason', v_status);
  end if;
  select pg_catalog.lower(pg_catalog.btrim(email)) into v_email from auth.users where id = p_owner_id;
  insert into private.founder_trial_claims (owner_id, email_digest, workspace_id, claimed_at)
  values (p_owner_id, extensions.digest(v_email, 'sha256'), p_workspace_id, v_now)
  on conflict do nothing returning owner_id into v_claimed;
  if v_claimed is null then
    return pg_catalog.jsonb_build_object('reason', 'already_claimed');
  end if;
  update public.workspaces
     set trial_started_at = v_now, trial_expires_at = v_now + interval '168 hours'
   where id = p_workspace_id and owner_id = p_owner_id
     and plan = 'free' and billing_status = 'none'
     and trial_started_at is null and trial_expires_at is null;
  if not found then
    raise exception 'workspace changed during trial activation' using errcode = '40001';
  end if;
  return pg_catalog.jsonb_build_object('reason', 'activated', 'trial_started_at', v_now,
    'trial_expires_at', v_now + interval '168 hours');
end;
$$;
revoke all on function public.claim_existing_user_trial(uuid, uuid) from public, anon, authenticated;
grant execute on function public.claim_existing_user_trial(uuid, uuid) to service_role;
