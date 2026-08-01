-- Task approval workflow for Team workspaces.
alter table public.tasks
  add column if not exists approval_status text not null default 'not_required'
    check (approval_status in ('not_required', 'pending', 'approved', 'rejected')),
  add column if not exists approval_submitted_by uuid references public.profiles (id) on delete set null,
  add column if not exists approval_reviewed_by uuid references public.profiles (id) on delete set null,
  add column if not exists approval_reviewed_at timestamptz,
  add column if not exists approval_note text;

create index if not exists idx_tasks_approval
  on public.tasks (workspace_id, approval_status);
