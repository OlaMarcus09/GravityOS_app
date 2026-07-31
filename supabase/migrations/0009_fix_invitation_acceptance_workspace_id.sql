-- Fix accept_workspace_invitation() for databases that already applied 0008.
-- The function returns a column named workspace_id; using an unqualified
-- ON CONFLICT (workspace_id, user_id) therefore raises PostgreSQL 42702.
create or replace function public.accept_workspace_invitation(invitation_id uuid)
returns table (membership_id uuid, workspace_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
declare
  invitation public.workspace_invitations%rowtype;
  new_membership_id uuid;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;

  select * into invitation
  from public.workspace_invitations wi
  where wi.id = invitation_id
  for update;

  if invitation.id is null
     or invitation.email <> lower(coalesce(auth.jwt() ->> 'email', '')) then
    raise exception 'invitation not found' using errcode = 'P0002';
  end if;
  if invitation.accepted_at is not null or invitation.revoked_at is not null then
    raise exception 'invitation is no longer available' using errcode = '23514';
  end if;
  if invitation.expires_at <= now() then
    raise exception 'invitation has expired' using errcode = '22023';
  end if;

  insert into public.workspace_members (
    workspace_id, user_id, role, invited_at, joined_at
  ) values (
    invitation.workspace_id, auth.uid(), invitation.role, invitation.invited_at, now()
  )
  on conflict on constraint workspace_members_workspace_id_user_id_key do update
    set joined_at = coalesce(public.workspace_members.joined_at, excluded.joined_at)
  returning id into new_membership_id;

  update public.workspace_invitations
  set accepted_at = now()
  where id = invitation.id;

  return query select new_membership_id, invitation.workspace_id;
end;
$$;

revoke all on function public.accept_workspace_invitation(uuid) from public;
grant execute on function public.accept_workspace_invitation(uuid) to authenticated;
