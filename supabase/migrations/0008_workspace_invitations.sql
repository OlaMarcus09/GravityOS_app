-- Email-first workspace invitations. Membership is only created after the
-- authenticated recipient accepts the invitation.

create table public.workspace_invitations (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  email        text not null,
  role         public.member_role not null default 'member',
  invited_by   uuid not null references public.profiles (id) on delete cascade,
  invited_at   timestamptz not null default now(),
  expires_at   timestamptz not null default (now() + interval '7 days'),
  accepted_at  timestamptz,
  revoked_at   timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz,
  constraint workspace_invitations_email_normalized
    check (email = lower(btrim(email))),
  constraint workspace_invitations_role
    check (role <> 'owner'),
  unique (workspace_id, email)
);

create index workspace_invitations_recipient_idx
  on public.workspace_invitations (email, expires_at);
create index workspace_invitations_workspace_idx
  on public.workspace_invitations (workspace_id, invited_at desc);

alter table public.workspace_invitations enable row level security;

-- Owners/admins manage invitations for their workspace. Recipients can see
-- invitations addressed to the email in their verified JWT.
create policy workspace_invitations_select on public.workspace_invitations
  for select using (
    private.has_workspace_role(
      workspace_id,
      array['owner','admin']::public.member_role[]
    )
    or email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );

create policy workspace_invitations_insert on public.workspace_invitations
  for insert with check (
    private.has_workspace_role(
      workspace_id,
      array['owner','admin']::public.member_role[]
    )
    and invited_by = auth.uid()
  );

create policy workspace_invitations_update on public.workspace_invitations
  for update using (
    private.has_workspace_role(
      workspace_id,
      array['owner','admin']::public.member_role[]
    )
  ) with check (
    private.has_workspace_role(
      workspace_id,
      array['owner','admin']::public.member_role[]
    )
  );

create policy workspace_invitations_delete on public.workspace_invitations
  for delete using (
    private.has_workspace_role(
      workspace_id,
      array['owner','admin']::public.member_role[]
    )
  );

create trigger set_workspace_invitations_updated_at
before update on public.workspace_invitations
for each row execute function public.set_updated_at();

-- Accepting an invitation must create the membership and consume the invite in
-- one transaction. The function verifies the authenticated recipient itself.
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
  on conflict (workspace_id, user_id) do update
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
