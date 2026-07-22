-- Gravity OS — auto-provision a default workspace on signup.
-- Extends private.handle_new_user (which already mirrors a profile row) so that
-- every new auth.users row also gets a personal workspace plus an owner
-- membership. Without this, a fresh account has no workspace and every
-- feature write fails because the X-Workspace-Id it would send doesn't exist.

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_name text := coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1));
  v_workspace_id uuid;
begin
  insert into public.profiles (id, display_name)
  values (new.id, v_name)
  on conflict (id) do nothing;

  -- Give the new user a personal workspace to write into.
  insert into public.workspaces (name, owner_id, type)
  values (v_name || '''s Studio', new.id, 'personal')
  returning id into v_workspace_id;

  insert into public.workspace_members (workspace_id, user_id, role)
  values (v_workspace_id, new.id, 'owner');

  return new;
end;
$$;
