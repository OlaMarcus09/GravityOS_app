-- Make the approval decision the terminal completion action for Team tasks.
-- Rejections reopen the task for corrections while the immutable decision
-- history remains in task_approval_events.
create or replace function private.guard_task_approval_columns()
returns trigger
language plpgsql
as $$
begin
  if current_setting('gravity.approval_mutation', true) <> 'true' then
    if old.approval_status in ('pending', 'approved') and new is distinct from old then
      raise exception 'pending and approved tasks are locked';
    end if;
    if (new.approval_status, new.approval_submitted_by, new.approval_reviewed_by,
        new.approval_reviewed_at, new.approval_note)
       is distinct from
       (old.approval_status, old.approval_submitted_by, old.approval_reviewed_by,
        old.approval_reviewed_at, old.approval_note) then
      raise exception 'approval fields are server-controlled';
    end if;
  end if;
  return new;
end;
$$;

create or replace function private.guard_locked_task_deletion()
returns trigger
language plpgsql
as $$
begin
  if old.approval_status in ('pending', 'approved', 'rejected') then
    raise exception 'reviewed tasks cannot be deleted because approval history is immutable';
  end if;
  return old;
end;
$$;

drop trigger if exists tasks_guard_locked_deletion on public.tasks;
create trigger tasks_guard_locked_deletion
before delete on public.tasks
for each row execute function private.guard_locked_task_deletion();

create or replace function public.review_task_approval(
  p_task_id uuid,
  p_decision text,
  p_note text default null
)
returns public.tasks
language plpgsql security definer
set search_path = public, private
as $$
declare current_task public.tasks;
declare changed public.tasks;
declare decision_at timestamptz := now();
begin
  if p_decision not in ('approved', 'rejected') then
    raise exception 'invalid approval decision' using errcode = '22023';
  end if;

  select t.* into current_task
  from public.tasks t
  join public.workspaces w on w.id = t.workspace_id
  where t.id = p_task_id
    and w.plan = 'team'
    and private.has_workspace_role(
      t.workspace_id,
      array['owner','admin']::public.member_role[]
    )
  for update;

  if not found then
    raise exception 'task not found or reviewer access required' using errcode = '42501';
  end if;
  if current_task.approval_status <> 'pending' then
    raise exception 'task is not awaiting approval' using errcode = '40001';
  end if;
  if current_task.approval_submitted_by = auth.uid() then
    raise exception 'submitter cannot review their own task' using errcode = '42501';
  end if;

  perform set_config('gravity.approval_mutation', 'true', true);
  update public.tasks
  set approval_status = p_decision,
      approval_reviewed_by = auth.uid(),
      approval_reviewed_at = decision_at,
      approval_note = nullif(left(p_note, 1000), ''),
      status = case
        when p_decision = 'approved' then 'done'::public.task_status
        else 'todo'::public.task_status
      end,
      completed_at = case
        when p_decision = 'approved' then decision_at
        else null
      end
  where id = p_task_id
    and approval_status = 'pending'
  returning * into changed;

  if not found then
    raise exception 'task review conflict' using errcode = '40001';
  end if;

  insert into public.task_approval_events(
    task_id, workspace_id, actor_id, from_status, to_status, note
  ) values (
    p_task_id, changed.workspace_id, auth.uid(), 'pending', p_decision,
    changed.approval_note
  );

  return changed;
end;
$$;

revoke all on function public.review_task_approval(uuid, text, text) from public, anon;
grant execute on function public.review_task_approval(uuid, text, text) to authenticated;
