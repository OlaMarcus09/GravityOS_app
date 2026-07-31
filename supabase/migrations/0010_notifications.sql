-- Persistent in-app notifications for authenticated users and invited emails.
create table public.notifications (
  id              uuid primary key default gen_random_uuid(),
  workspace_id    uuid references public.workspaces (id) on delete cascade,
  recipient_id    uuid references public.profiles (id) on delete cascade,
  recipient_email text,
  kind            text not null,
  title           text not null,
  message         text not null,
  action_url      text,
  metadata        jsonb not null default '{}'::jsonb,
  read_at         timestamptz,
  created_at      timestamptz not null default now(),
  constraint notifications_recipient_required
    check (recipient_id is not null or recipient_email is not null),
  constraint notifications_email_normalized
    check (recipient_email is null or recipient_email = lower(btrim(recipient_email)))
);

create index notifications_recipient_id_idx
  on public.notifications (recipient_id, created_at desc);
create index notifications_recipient_email_idx
  on public.notifications (recipient_email, created_at desc);
create index notifications_unread_idx
  on public.notifications (recipient_id, created_at desc) where read_at is null;

alter table public.notifications enable row level security;

create policy notifications_select_own on public.notifications
  for select using (
    recipient_id = auth.uid()
    or recipient_email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );

create policy notifications_update_own on public.notifications
  for update using (
    recipient_id = auth.uid()
    or recipient_email = lower(coalesce(auth.jwt() ->> 'email', ''))
  ) with check (
    recipient_id = auth.uid()
    or recipient_email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );

create policy notifications_delete_own on public.notifications
  for delete using (
    recipient_id = auth.uid()
    or recipient_email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );

revoke insert on public.notifications from anon, authenticated;
