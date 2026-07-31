-- Project/task discussions and the workspace activity feed.
create type public.collaboration_target_type as enum ('project', 'task');

create table public.comments (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  target_type  public.collaboration_target_type not null,
  target_id    uuid not null,
  author_id    uuid not null references public.profiles (id) on delete cascade,
  body         text not null check (char_length(btrim(body)) between 1 and 5000),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz
);

create index comments_target_idx
  on public.comments (workspace_id, target_type, target_id, created_at);
create index comments_author_idx on public.comments (author_id, created_at desc);

create or replace function private.validate_collaboration_target()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
begin
  if new.target_type = 'project' and not exists (
    select 1 from public.projects
    where id = new.target_id and workspace_id = new.workspace_id
  ) then
    raise exception 'project does not belong to workspace';
  elsif new.target_type = 'task' and not exists (
    select 1 from public.tasks
    where id = new.target_id and workspace_id = new.workspace_id
  ) then
    raise exception 'task does not belong to workspace';
  end if;
  return new;
end;
$$;

create trigger comments_validate_target
before insert or update of workspace_id, target_type, target_id on public.comments
for each row execute function private.validate_collaboration_target();

create trigger comments_set_updated_at
before update on public.comments
for each row execute function public.set_updated_at();

create table public.workspace_activity_events (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  actor_id     uuid references public.profiles (id) on delete set null,
  event_type   text not null,
  target_type  public.collaboration_target_type,
  target_id    uuid,
  summary      text not null,
  metadata     jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now(),
  constraint activity_target_complete check (
    (target_type is null and target_id is null)
    or (target_type is not null and target_id is not null)
  )
);

create index activity_workspace_idx
  on public.workspace_activity_events (workspace_id, created_at desc);
create index activity_target_idx
  on public.workspace_activity_events (workspace_id, target_type, target_id, created_at desc);

create trigger activity_validate_target
before insert or update of workspace_id, target_type, target_id on public.workspace_activity_events
for each row
when (new.target_type is not null)
execute function private.validate_collaboration_target();

alter table public.comments enable row level security;
alter table public.workspace_activity_events enable row level security;

create policy comments_select_member on public.comments
  for select using (private.is_workspace_member(workspace_id));
create policy comments_insert_writer on public.comments
  for insert with check (
    private.is_workspace_writer(workspace_id)
    and author_id = auth.uid()
  );
create policy comments_update_author on public.comments
  for update using (
    author_id = auth.uid() and private.is_workspace_writer(workspace_id)
  ) with check (
    author_id = auth.uid() and private.is_workspace_writer(workspace_id)
  );
create policy comments_delete_author_or_admin on public.comments
  for delete using (
    (author_id = auth.uid() and private.is_workspace_writer(workspace_id))
    or private.has_workspace_role(
      workspace_id,
      array['owner', 'admin']::public.member_role[]
    )
  );

create policy activity_select_member on public.workspace_activity_events
  for select using (private.is_workspace_member(workspace_id));

-- Activity events are server-owned audit records. Authenticated users can
-- read their workspace feed but cannot forge, edit, or delete events.
revoke insert, update, delete on public.workspace_activity_events from anon, authenticated;

-- Team members need basic identity fields to render comment authors/activity.
create policy profiles_select_shared_workspace on public.profiles
  for select using (
    exists (
      select 1
      from public.workspace_members mine
      join public.workspace_members theirs
        on theirs.workspace_id = mine.workspace_id
      where mine.user_id = auth.uid()
        and theirs.user_id = profiles.id
    )
  );
