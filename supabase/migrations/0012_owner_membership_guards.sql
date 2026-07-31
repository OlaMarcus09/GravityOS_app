-- Keep the workspace owner membership aligned with workspaces.owner_id even
-- when a privileged backend client bypasses row-level security.
create or replace function public.guard_workspace_owner_membership()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  workspace_owner uuid;
begin
  select owner_id
    into workspace_owner
    from public.workspaces
   where id = new.workspace_id;

  if tg_op = 'UPDATE'
     and (old.user_id = workspace_owner or old.role = 'owner') then
    raise exception 'workspace owner membership cannot be modified';
  end if;

  if new.user_id = workspace_owner and new.role <> 'owner' then
    raise exception 'workspace owner must have the owner role';
  end if;
  if new.role = 'owner' and new.user_id <> workspace_owner then
    raise exception 'owner role is reserved for the workspace owner';
  end if;

  return new;
end;
$$;

create or replace function public.guard_workspace_owner_membership_delete()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- Parent deletion cascades are valid; the workspace no longer exists then.
  if exists (
    select 1
      from public.workspaces
     where id = old.workspace_id
       and (owner_id = old.user_id or old.role = 'owner')
  ) then
    raise exception 'workspace owner membership cannot be deleted';
  end if;
  return old;
end;
$$;

drop trigger if exists guard_workspace_owner_membership on public.workspace_members;
create trigger guard_workspace_owner_membership
before insert or update on public.workspace_members
for each row execute function public.guard_workspace_owner_membership();

drop trigger if exists guard_workspace_owner_membership_delete on public.workspace_members;
create trigger guard_workspace_owner_membership_delete
after delete on public.workspace_members
for each row execute function public.guard_workspace_owner_membership_delete();
