-- Private promotional invitation state. No customer send is enabled by this migration.
create table private.trial_invitation_deliveries (
  id uuid primary key default gen_random_uuid(),
  campaign text not null default 'existing_user_trial_2026',
  kind text not null check (kind in ('initial', 'reminder', 'test')),
  owner_id uuid,
  workspace_id uuid,
  email_digest bytea not null,
  state text not null default 'prepared' check (state in
    ('prepared', 'attempting', 'accepted', 'delivered', 'failed', 'bounced', 'complained', 'uncertain')),
  eligibility_verified_at timestamptz,
  suppression_verified_at timestamptz,
  attempted_at timestamptz,
  accepted_at timestamptz,
  delivered_at timestamptz,
  last_event_at timestamptz,
  provider_message_id text unique,
  provider_error_code text,
  idempotency_key uuid not null default gen_random_uuid(),
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  constraint trial_invite_test_identity check (
    (kind = 'test' and owner_id is null and workspace_id is null)
    or (kind <> 'test' and owner_id is not null and workspace_id is not null)
  )
);
create unique index trial_invite_one_per_email
  on private.trial_invitation_deliveries(campaign, kind, email_digest);
create unique index trial_invite_one_per_owner
  on private.trial_invitation_deliveries(campaign, kind, owner_id) where owner_id is not null;
create index trial_invite_provider_reconcile
  on private.trial_invitation_deliveries(state, attempted_at)
  where state in ('attempting', 'accepted', 'uncertain');
revoke all on private.trial_invitation_deliveries from public, anon, authenticated;
alter table private.trial_invitation_deliveries enable row level security;

create table private.trial_invitation_opt_outs (
  email_digest bytea primary key,
  owner_id uuid,
  source_delivery_id uuid references private.trial_invitation_deliveries(id),
  created_at timestamptz not null default clock_timestamp()
);
create index trial_invite_opt_out_owner on private.trial_invitation_opt_outs(owner_id);
revoke all on private.trial_invitation_opt_outs from public, anon, authenticated;
alter table private.trial_invitation_opt_outs enable row level security;

-- The API authenticates the single-purpose HMAC token before invoking this
-- service-only function. The function reveals no recipient information.
create function public.record_trial_invitation_opt_out(p_delivery_id uuid)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare v_delivery private.trial_invitation_deliveries%rowtype;
begin
  select * into v_delivery from private.trial_invitation_deliveries
    where id = p_delivery_id;
  if not found then return false; end if;
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(pg_catalog.encode(v_delivery.email_digest, 'hex'), 0));
  insert into private.trial_invitation_opt_outs
    (email_digest, owner_id, source_delivery_id)
    values (v_delivery.email_digest, v_delivery.owner_id, v_delivery.id)
    on conflict (email_digest) do nothing;
  return true;
end;
$$;
revoke all on function public.record_trial_invitation_opt_out(uuid) from public, anon, authenticated;
grant execute on function public.record_trial_invitation_opt_out(uuid) to service_role;
