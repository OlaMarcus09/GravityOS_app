-- Restrict co-member profile access to API-selected public identity fields.
-- The API hydrates display_name/avatar_url with its service client; users keep
-- the original profiles_select_own policy for their complete profile.
drop policy if exists profiles_select_shared_workspace on public.profiles;

-- Tie invitation notifications to the authenticated recipient after accept,
-- and remove them when the corresponding invitation is revoked.
create or replace function private.sync_invitation_notification_recipient()
returns trigger
language plpgsql
security definer
set search_path = public, private
as $$
begin
  if new.accepted_at is not null and old.accepted_at is null then
    update public.notifications
    set recipient_id = auth.uid(),
        recipient_email = null,
        read_at = coalesce(read_at, now())
    where workspace_id = new.workspace_id
      and recipient_email = new.email
      and metadata ->> 'invitation_id' = new.id::text;
  elsif new.revoked_at is not null and old.revoked_at is null then
    delete from public.notifications
    where workspace_id = new.workspace_id
      and recipient_email = new.email
      and metadata ->> 'invitation_id' = new.id::text;
  end if;
  return new;
end;
$$;

drop trigger if exists workspace_invitations_sync_notifications
  on public.workspace_invitations;
create trigger workspace_invitations_sync_notifications
after update of accepted_at, revoked_at on public.workspace_invitations
for each row execute function private.sync_invitation_notification_recipient();
