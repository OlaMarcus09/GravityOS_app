-- Retention outreach state. These rows are service-owned so users cannot
-- reset their dormancy period or manufacture a second check-in.
alter table public.notification_preferences
  add column activation_nudges boolean not null default true,
  add column weekly_digests boolean not null default true,
  add column dormant_checkins boolean not null default true;

create table public.retention_checkins (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references public.profiles (id) on delete cascade,
  kind               text not null,
  period_started_at  timestamptz not null,
  dedupe_key         text not null unique,
  sent_at            timestamptz not null default now(),
  created_at         timestamptz not null default now(),
  constraint retention_checkins_kind_present check (btrim(kind) <> '')
);

create unique index retention_checkins_user_period_uidx
  on public.retention_checkins (user_id, kind, period_started_at);

create index retention_checkins_user_idx
  on public.retention_checkins (user_id, sent_at desc);

alter table public.retention_checkins enable row level security;
revoke all on public.retention_checkins from anon, authenticated;
