-- Billing foundation for manual annual Flutterwave checkout.
-- This migration adds durable billing state only. It does not call
-- Flutterwave, expose checkout endpoints, or implement renewal jobs.

do $$
begin
  create type public.workspace_billing_status as enum ('none', 'active', 'expired', 'manual');
exception
  when duplicate_object then null;
end $$;

do $$
begin
  create type public.billing_period as enum ('annual');
exception
  when duplicate_object then null;
end $$;

do $$
begin
  create type public.billing_transaction_status as enum (
    'initiated',
    'pending',
    'paid',
    'failed',
    'cancelled'
  );
exception
  when duplicate_object then null;
end $$;

do $$
begin
  create type public.billing_webhook_processing_status as enum (
    'received',
    'processed',
    'ignored',
    'failed'
  );
exception
  when duplicate_object then null;
end $$;

alter table public.workspaces
  add column if not exists billing_country text,
  add column if not exists billing_status public.workspace_billing_status not null default 'none',
  add column if not exists current_period_start timestamptz,
  add column if not exists current_period_end timestamptz,
  add column if not exists last_billing_transaction_id uuid;

alter table public.workspaces
  drop constraint if exists workspaces_billing_country_shape,
  add constraint workspaces_billing_country_shape
    check (billing_country is null or billing_country ~ '^[A-Z]{2}$'),
  drop constraint if exists workspaces_billing_period_order,
  add constraint workspaces_billing_period_order
    check (
      current_period_start is null
      or current_period_end is null
      or current_period_end > current_period_start
    );

-- Existing paid workspaces were granted manually before self-service billing.
update public.workspaces
set billing_status = 'manual'
where plan in ('pro', 'team', 'enterprise')
  and billing_status = 'none';

create or replace function private.normalize_workspace_billing_country()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
begin
  if new.billing_country is not null then
    new.billing_country = nullif(upper(btrim(new.billing_country)), '');
  end if;
  return new;
end;
$$;

drop trigger if exists normalize_workspace_billing_country on public.workspaces;
create trigger normalize_workspace_billing_country
before insert or update of billing_country on public.workspaces
for each row execute function private.normalize_workspace_billing_country();

create table if not exists public.billing_transactions (
  id                         uuid primary key default gen_random_uuid(),
  workspace_id               uuid not null references public.workspaces (id) on delete restrict,
  initiated_by               uuid references public.profiles (id) on delete set null,
  provider                   text not null default 'flutterwave',
  tx_ref                     text not null,
  provider_transaction_id    text,
  provider_flw_ref           text,
  requested_plan             public.workspace_plan not null,
  billing_period             public.billing_period not null default 'annual',
  expected_amount            numeric(12,2) not null,
  expected_currency          text not null,
  internal_status            public.billing_transaction_status not null default 'initiated',
  provider_status            text,
  provider_verified_amount   numeric(12,2),
  provider_verified_currency text,
  paid_at                    timestamptz,
  verified_at                timestamptz,
  activated_at               timestamptz,
  entitlement_period_start   timestamptz,
  entitlement_period_end     timestamptz,
  failure_code               text,
  failure_message            text,
  created_at                 timestamptz not null default now(),
  updated_at                 timestamptz,
  constraint billing_transactions_tx_ref_nonempty
    check (btrim(tx_ref) <> ''),
  constraint billing_transactions_provider_nonempty
    check (btrim(provider) <> ''),
  constraint billing_transactions_amount_positive
    check (expected_amount > 0),
  constraint billing_transactions_verified_amount_positive
    check (provider_verified_amount is null or provider_verified_amount > 0),
  constraint billing_transactions_currency_shape
    check (expected_currency ~ '^[A-Z]{3}$'),
  constraint billing_transactions_verified_currency_shape
    check (provider_verified_currency is null or provider_verified_currency ~ '^[A-Z]{3}$'),
  constraint billing_transactions_self_service_plan
    check (requested_plan in ('pro', 'team')),
  constraint billing_transactions_entitlement_period_order
    check (
      entitlement_period_start is null
      or entitlement_period_end is null
      or entitlement_period_end > entitlement_period_start
    ),
  constraint billing_transactions_activation_consistency
    check (
      (activated_at is null and entitlement_period_start is null and entitlement_period_end is null)
      or (activated_at is not null and entitlement_period_start is not null and entitlement_period_end is not null)
    )
);

create unique index if not exists billing_transactions_tx_ref_uidx
  on public.billing_transactions (tx_ref);

create unique index if not exists billing_transactions_provider_transaction_uidx
  on public.billing_transactions (provider, provider_transaction_id)
  where provider_transaction_id is not null;

create index if not exists billing_transactions_workspace_created_idx
  on public.billing_transactions (workspace_id, created_at desc);

create index if not exists billing_transactions_status_created_idx
  on public.billing_transactions (internal_status, created_at desc);

create index if not exists billing_transactions_provider_lookup_idx
  on public.billing_transactions (provider, tx_ref);

drop trigger if exists billing_transactions_set_updated_at on public.billing_transactions;
create trigger billing_transactions_set_updated_at
before update on public.billing_transactions
for each row execute function public.set_updated_at();

alter table public.workspaces
  drop constraint if exists workspaces_last_billing_transaction_fk,
  add constraint workspaces_last_billing_transaction_fk
    foreign key (last_billing_transaction_id)
    references public.billing_transactions (id)
    on delete set null;

create table if not exists public.billing_webhook_events (
  id                       uuid primary key default gen_random_uuid(),
  provider                 text not null default 'flutterwave',
  provider_event_id        text not null,
  event_type               text,
  tx_ref                   text,
  provider_transaction_id  text,
  raw_body_sha256          text,
  processing_status        public.billing_webhook_processing_status not null default 'received',
  error_code               text,
  error_message            text,
  received_at              timestamptz not null default now(),
  processed_at             timestamptz,
  constraint billing_webhook_events_provider_nonempty
    check (btrim(provider) <> ''),
  constraint billing_webhook_events_provider_event_nonempty
    check (btrim(provider_event_id) <> ''),
  constraint billing_webhook_events_raw_body_sha256_shape
    check (raw_body_sha256 is null or raw_body_sha256 ~ '^[0-9a-f]{64}$')
);

create unique index if not exists billing_webhook_events_provider_event_uidx
  on public.billing_webhook_events (provider, provider_event_id);

create index if not exists billing_webhook_events_tx_ref_idx
  on public.billing_webhook_events (provider, tx_ref)
  where tx_ref is not null;

create index if not exists billing_webhook_events_processing_idx
  on public.billing_webhook_events (processing_status, received_at);

alter table public.billing_transactions enable row level security;
alter table public.billing_webhook_events enable row level security;

create policy billing_transactions_select_member on public.billing_transactions
  for select using (private.is_workspace_member(workspace_id));

revoke insert, update, delete on public.billing_transactions from anon, authenticated;
revoke all on public.billing_webhook_events from anon, authenticated;

-- Authenticated owner/admin users may eventually set billing_country through
-- the existing workspaces_update_admin policy, but all entitlement fields stay
-- service-owned. This preserves workspaces.plan as the authoritative gate.
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
    or new.billing_status is distinct from old.billing_status
    or new.current_period_start is distinct from old.current_period_start
    or new.current_period_end is distinct from old.current_period_end
    or new.last_billing_transaction_id is distinct from old.last_billing_transaction_id
  ) then
    raise exception 'workspace plan, ownership, or billing entitlement changes require the admin service'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

drop trigger if exists prevent_client_plan_change on public.workspaces;
create trigger prevent_client_plan_change
before update of plan, owner_id, billing_status, current_period_start, current_period_end, last_billing_transaction_id on public.workspaces
for each row execute function private.prevent_client_plan_change();

create or replace function public.activate_billing_transaction(
  p_billing_transaction_id uuid,
  p_verified_at timestamptz default now(),
  p_paid_at timestamptz default null
)
returns public.billing_transactions
language plpgsql
security definer
set search_path = public, private
as $$
declare
  txn public.billing_transactions;
  ws public.workspaces;
  start_at timestamptz;
  end_at timestamptz;
  activated public.billing_transactions;
begin
  select *
  into txn
  from public.billing_transactions
  where id = p_billing_transaction_id
  for update;

  if not found then
    raise exception 'billing transaction not found' using errcode = 'P0002';
  end if;

  if txn.activated_at is not null then
    return txn;
  end if;

  if txn.internal_status not in ('initiated', 'pending') then
    raise exception 'billing transaction is not eligible for activation' using errcode = '42501';
  end if;

  if txn.requested_plan not in ('pro', 'team') then
    raise exception 'only Pro or Team can be activated through self-service billing' using errcode = '42501';
  end if;

  select *
  into ws
  from public.workspaces
  where id = txn.workspace_id
  for update;

  if not found then
    raise exception 'workspace not found' using errcode = 'P0002';
  end if;

  if ws.plan = 'enterprise' or ws.billing_status = 'manual' then
    raise exception 'manual or enterprise workspaces cannot be converted through self-service billing'
      using errcode = '42501';
  end if;

  if ws.billing_status = 'active'
     and ws.current_period_end is not null
     and ws.current_period_end > now() then
    start_at = ws.current_period_end;
  else
    start_at = now();
  end if;
  end_at = start_at + interval '1 year';

  update public.workspaces
  set plan = txn.requested_plan,
      billing_status = 'active',
      current_period_start = start_at,
      current_period_end = end_at,
      last_billing_transaction_id = txn.id,
      updated_at = now()
  where id = ws.id;

  update public.billing_transactions
  set internal_status = 'paid',
      paid_at = coalesce(p_paid_at, p_verified_at, now()),
      verified_at = coalesce(p_verified_at, now()),
      activated_at = now(),
      entitlement_period_start = start_at,
      entitlement_period_end = end_at,
      failure_code = null,
      failure_message = null
  where id = txn.id
  returning * into activated;

  return activated;
end;
$$;

revoke all on function public.activate_billing_transaction(uuid, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.activate_billing_transaction(uuid, timestamptz, timestamptz)
  to service_role;

revoke all on function private.normalize_workspace_billing_country() from public;
revoke all on function private.prevent_client_plan_change() from public;
