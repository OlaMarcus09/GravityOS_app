-- Harden Team approval transitions and preserve decision history.
create table if not exists public.task_approval_events (
  id          uuid primary key default gen_random_uuid(),
  task_id     uuid not null references public.tasks (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  actor_id    uuid not null references public.profiles (id) on delete restrict,
  from_status text not null,
  to_status   text not null,
  note        text,
  created_at  timestamptz not null default now()
);

create index if not exists idx_task_approval_events_task
  on public.task_approval_events (task_id, created_at desc);

alter table public.task_approval_events enable row level security;
create policy task_approval_events_select_member on public.task_approval_events
  for select using (private.is_workspace_member(workspace_id));
revoke insert, update, delete on public.task_approval_events from anon, authenticated;

create or replace function private.guard_task_approval_columns()
returns trigger
language plpgsql
as $$
begin
  if (new.approval_status, new.approval_submitted_by, new.approval_reviewed_by,
      new.approval_reviewed_at, new.approval_note)
     is distinct from
     (old.approval_status, old.approval_submitted_by, old.approval_reviewed_by,
      old.approval_reviewed_at, old.approval_note)
     and current_setting('gravity.approval_mutation', true) <> 'true' then
    raise exception 'approval fields are server-controlled';
  end if;
  return new;
end;
$$;

drop trigger if exists tasks_guard_approval_columns on public.tasks;
create trigger tasks_guard_approval_columns
before update on public.tasks
for each row execute function private.guard_task_approval_columns();

create or replace function public.submit_task_for_approval(p_task_id uuid)
returns public.tasks
language plpgsql security definer
set search_path = public, private
as $$
declare current_task public.tasks;
declare changed public.tasks;
begin
  select t.* into current_task from public.tasks t
  join public.workspaces w on w.id = t.workspace_id
  where t.id = p_task_id and private.is_workspace_writer(t.workspace_id) and w.plan = 'team'
  for update;
  if not found then raise exception 'task not found or Team access required' using errcode = '42501'; end if;
  if current_task.approval_status = 'pending' then return current_task; end if;
  perform set_config('gravity.approval_mutation', 'true', true);
  update public.tasks set approval_status = 'pending', approval_submitted_by = auth.uid(),
    approval_reviewed_by = null, approval_reviewed_at = null, approval_note = null
    where id = p_task_id returning * into changed;
  insert into public.task_approval_events(task_id, workspace_id, actor_id, from_status, to_status)
    values (p_task_id, changed.workspace_id, auth.uid(), current_task.approval_status, 'pending');
  return changed;
end;
$$;

create or replace function public.review_task_approval(p_task_id uuid, p_decision text, p_note text default null)
returns public.tasks
language plpgsql security definer
set search_path = public, private
as $$
declare current_task public.tasks;
declare changed public.tasks;
begin
  if p_decision not in ('approved', 'rejected') then raise exception 'invalid approval decision' using errcode = '22023'; end if;
  select t.* into current_task from public.tasks t
  join public.workspaces w on w.id = t.workspace_id
  where t.id = p_task_id and w.plan = 'team'
    and private.has_workspace_role(t.workspace_id, array['owner','admin']::public.member_role[])
  for update;
  if not found then raise exception 'task not found or reviewer access required' using errcode = '42501'; end if;
  if current_task.approval_status <> 'pending' then raise exception 'task is not awaiting approval' using errcode = '40001'; end if;
  if current_task.approval_submitted_by = auth.uid() then raise exception 'submitter cannot review their own task' using errcode = '42501'; end if;
  perform set_config('gravity.approval_mutation', 'true', true);
  update public.tasks set approval_status = p_decision, approval_reviewed_by = auth.uid(),
    approval_reviewed_at = now(), approval_note = nullif(left(p_note, 1000), '')
    where id = p_task_id and approval_status = 'pending' returning * into changed;
  if not found then raise exception 'task review conflict' using errcode = '40001'; end if;
  insert into public.task_approval_events(task_id, workspace_id, actor_id, from_status, to_status, note)
    values (p_task_id, changed.workspace_id, auth.uid(), 'pending', p_decision, changed.approval_note);
  return changed;
end;
$$;

revoke all on function public.submit_task_for_approval(uuid) from public, anon;
revoke all on function public.review_task_approval(uuid, text, text) from public, anon;
grant execute on function public.submit_task_for_approval(uuid) to authenticated;
grant execute on function public.review_task_approval(uuid, text, text) to authenticated;

-- Keep direct PostgREST membership mutations aligned with the API hierarchy.
drop policy if exists members_update_admin on public.workspace_members;
create policy members_update_admin on public.workspace_members
  for update using (
    private.has_workspace_role(workspace_id, array['owner','admin']::public.member_role[])
    and (private.has_workspace_role(workspace_id, array['owner']::public.member_role[]) or role <> 'admin')
  ) with check (
    private.has_workspace_role(workspace_id, array['owner','admin']::public.member_role[])
    and (private.has_workspace_role(workspace_id, array['owner']::public.member_role[]) or role <> 'admin')
  );

drop policy if exists members_delete_admin on public.workspace_members;
create policy members_delete_admin on public.workspace_members
  for delete using (
    private.has_workspace_role(workspace_id, array['owner','admin']::public.member_role[])
    and (private.has_workspace_role(workspace_id, array['owner']::public.member_role[]) or role <> 'admin')
  );

create or replace function private.guard_admin_invitations()
returns trigger
language plpgsql
as $$
begin
  if new.role = 'admin' and not exists (
    select 1 from public.workspace_members
    where workspace_id = new.workspace_id and user_id = new.invited_by and role = 'owner'
  ) then
    raise exception 'only the workspace owner can invite administrators';
  end if;
  return new;
end;
$$;

drop trigger if exists workspace_invitations_guard_admin on public.workspace_invitations;
create trigger workspace_invitations_guard_admin
before insert or update of role, invited_by, workspace_id on public.workspace_invitations
for each row execute function private.guard_admin_invitations();

create or replace function private.guard_notification_recipient_workspace()
returns trigger
language plpgsql
as $$
begin
  if new.recipient_id is not null and new.workspace_id is not null and not exists (
    select 1 from public.workspace_members
    where workspace_id = new.workspace_id and user_id = new.recipient_id
  ) then
    raise exception 'notification recipient is not a workspace member';
  end if;
  return new;
end;
$$;

drop trigger if exists notifications_guard_recipient_workspace on public.notifications;
create trigger notifications_guard_recipient_workspace
before insert or update of recipient_id, workspace_id on public.notifications
for each row execute function private.guard_notification_recipient_workspace();
