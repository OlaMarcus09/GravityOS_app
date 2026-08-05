-- Proactive notification preferences and a service-owned email outbox.
-- Delivery workers and schedules are intentionally deferred to the API layer.

create table public.notification_preferences (
  user_id                   uuid primary key references public.profiles (id) on delete cascade,
  email_enabled             boolean not null default true,
  in_app_enabled            boolean not null default true,
  task_assignments          boolean not null default true,
  mentions                  boolean not null default true,
  approval_updates          boolean not null default true,
  deadline_reminders        boolean not null default true,
  reminder_days_before      integer[] not null default array[3, 1, 0],
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint notification_preferences_reminder_days_bounded
    check (
      cardinality(reminder_days_before) between 1 and 10
      and array_position(reminder_days_before, null) is null
      and 0 <= all(reminder_days_before)
      and 365 >= all(reminder_days_before)
    )
);

alter table public.notification_preferences enable row level security;

create policy notification_preferences_select_own
  on public.notification_preferences
  for select using (user_id = auth.uid());

create policy notification_preferences_insert_own
  on public.notification_preferences
  for insert with check (user_id = auth.uid());

create policy notification_preferences_update_own
  on public.notification_preferences
  for update using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy notification_preferences_delete_own
  on public.notification_preferences
  for delete using (user_id = auth.uid());

drop trigger if exists notification_preferences_set_updated_at
  on public.notification_preferences;
create trigger notification_preferences_set_updated_at
before update on public.notification_preferences
for each row execute function public.set_updated_at();

-- Existing notification rows remain valid: both columns are nullable and the
-- partial unique index ignores all pre-existing NULL dedupe keys.
alter table public.notifications
  add column if not exists dedupe_key text,
  add column if not exists emailed_at timestamptz;

create unique index if not exists notifications_dedupe_key_uidx
  on public.notifications (dedupe_key)
  where dedupe_key is not null;

create table public.email_deliveries (
  id                    uuid primary key default gen_random_uuid(),
  notification_id       uuid references public.notifications (id) on delete set null,
  workspace_id          uuid references public.workspaces (id) on delete cascade,
  recipient_id          uuid references public.profiles (id) on delete set null,
  recipient_email       text not null,
  template_key          text not null,
  subject               text not null,
  template_data         jsonb not null default '{}'::jsonb,
  status                text not null default 'pending',
  attempts              integer not null default 0,
  max_attempts          integer not null default 5,
  idempotency_key       text not null unique,
  next_attempt_at       timestamptz not null default now(),
  provider              text not null default 'resend',
  provider_message_id   text,
  last_error            text,
  sent_at               timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint email_deliveries_recipient_email_normalized
    check (recipient_email = lower(btrim(recipient_email)) and recipient_email <> ''),
  constraint email_deliveries_template_key_present
    check (btrim(template_key) <> ''),
  constraint email_deliveries_subject_present
    check (btrim(subject) <> ''),
  constraint email_deliveries_idempotency_key_present
    check (btrim(idempotency_key) <> ''),
  constraint email_deliveries_provider_present
    check (btrim(provider) <> ''),
  constraint email_deliveries_status_valid
    check (status in ('pending', 'processing', 'sent', 'failed', 'cancelled')),
  constraint email_deliveries_attempts_valid
    check (attempts >= 0 and max_attempts > 0 and attempts <= max_attempts),
  constraint email_deliveries_sent_state_valid
    check (
      (status = 'sent' and sent_at is not null)
      or (status <> 'sent' and sent_at is null)
    )
);

create index email_deliveries_retry_idx
  on public.email_deliveries (next_attempt_at, created_at)
  where status in ('pending', 'failed') and attempts < max_attempts;

create index email_deliveries_notification_idx
  on public.email_deliveries (notification_id)
  where notification_id is not null;

create index email_deliveries_recipient_idx
  on public.email_deliveries (recipient_email, created_at desc);

alter table public.email_deliveries enable row level security;

-- Outbox payloads, provider identifiers, and errors are operational data.
-- Only the service role may read or mutate them; no user-facing RLS policy is
-- created. In-app notification access remains governed by its existing RLS.
revoke all on public.email_deliveries from anon, authenticated;

drop trigger if exists email_deliveries_set_updated_at
  on public.email_deliveries;
create trigger email_deliveries_set_updated_at
before update on public.email_deliveries
for each row execute function public.set_updated_at();
