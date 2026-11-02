-- Run against an isolated database with 0032 applied. Never run on production.
begin;
do $$ begin
  if (select ends_at from private.existing_user_trial_campaign where singleton) <> '2026-11-15 22:59:59+00'::timestamptz
  then raise exception 'approved WAT deadline was not stored exactly'; end if;
end $$;
insert into auth.users (id,email,created_at,email_confirmed_at) values
 ('00000000-0000-0000-0000-000000000001','owner1@example.com','2026-10-01','2026-10-01'),
 ('00000000-0000-0000-0000-000000000002','owner2@example.com','2026-10-01',null),
 ('00000000-0000-0000-0000-000000000003','owner3@example.com','2026-10-01','2026-10-01'),
 ('00000000-0000-0000-0000-000000000004','owner4@example.com','2026-10-01','2026-10-01'),
 ('00000000-0000-0000-0000-000000000005','new@example.com','2026-11-02','2026-11-02'),
 ('00000000-0000-0000-0000-000000000006','owner6@example.com','2026-10-01','2026-10-01'),
 ('00000000-0000-0000-0000-000000000007','claimed@example.com','2026-10-01','2026-10-01'),
 ('00000000-0000-0000-0000-000000000008','CLAIMED@example.com','2026-10-01','2026-10-01');
insert into public.workspaces (id,owner_id,plan,billing_status) values
 ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001','free','none'),
 ('10000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-000000000001','free','none'),
 ('10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000002','free','none'),
 ('10000000-0000-0000-0000-000000000003','00000000-0000-0000-0000-000000000003','free','none'),
 ('10000000-0000-0000-0000-000000000004','00000000-0000-0000-0000-000000000004','free','none'),
 ('10000000-0000-0000-0000-000000000044','00000000-0000-0000-0000-000000000004','team','manual'),
 ('10000000-0000-0000-0000-000000000005','00000000-0000-0000-0000-000000000005','free','none'),
 ('10000000-0000-0000-0000-000000000006','00000000-0000-0000-0000-000000000006','free','none'),
 ('10000000-0000-0000-0000-000000000007','00000000-0000-0000-0000-000000000007','free','none'),
 ('10000000-0000-0000-0000-000000000008','00000000-0000-0000-0000-000000000008','free','none');
insert into public.workspace_members (workspace_id,user_id,role)
select id,owner_id,'owner' from public.workspaces;
insert into public.workspace_members (workspace_id,user_id,role) values
 ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000006','admin');
insert into private.founder_trial_claims (owner_id,email_digest,workspace_id,claimed_at)
values ('00000000-0000-0000-0000-000000000007',
 extensions.digest('claimed@example.com','sha256'),'10000000-0000-0000-0000-000000000007','2026-11-01');
insert into public.projects values ('10000000-0000-0000-0000-000000000001');
insert into public.tasks values ('10000000-0000-0000-0000-000000000001');
insert into public.comments values ('10000000-0000-0000-0000-000000000001');
insert into public.catalogue_items values ('10000000-0000-0000-0000-000000000001');

do $$
begin
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',clock_timestamp()) <> 'window_closed' then raise exception 'disabled campaign'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002',clock_timestamp()) <> 'email_confirmation_required' then raise exception 'unconfirmed'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000004','10000000-0000-0000-0000-000000000004',clock_timestamp()) <> 'paid_workspace_conflict' then raise exception 'paid conflict'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000005','10000000-0000-0000-0000-000000000005',clock_timestamp()) <> 'not_eligible' then raise exception 'new account'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000006','10000000-0000-0000-0000-000000000001',clock_timestamp()) <> 'not_owner' then raise exception 'admin claiming foreign'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000007',clock_timestamp()) <> 'already_claimed' then raise exception 'claim ledger'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000008','10000000-0000-0000-0000-000000000008',clock_timestamp()) <> 'already_claimed' then raise exception 'email digest ledger'; end if;
end $$;

update private.existing_user_trial_campaign set enabled=true, starts_at='2026-11-02 00:00:00+00';
do $$
declare
  first jsonb;
  again jsonb;
  started timestamptz;
  expires timestamptz;
begin
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','2026-11-02 00:00:00+00') <> 'eligible' then raise exception 'start boundary'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','2026-11-15 22:59:59.999999+00') <> 'eligible' then raise exception 'end inclusive second'; end if;
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','2026-11-15 23:00:00+00') <> 'window_closed' then raise exception 'end boundary'; end if;
  -- Keep the activation test independent of the CI runner's wall clock.
  update private.existing_user_trial_campaign set starts_at='2000-01-01', ends_at='2100-01-01';
  first := public.claim_existing_user_trial('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001');
  if first->>'reason' <> 'activated' then raise exception 'activation: %', first; end if;
  started := (first->>'trial_started_at')::timestamptz;
  expires := (first->>'trial_expires_at')::timestamptz;
  if extract(epoch from expires-started) <> 604800 then raise exception 'duration'; end if;
  again := public.claim_existing_user_trial('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000011');
  if again->>'reason' <> 'already_claimed' then raise exception 'multiple workspace claim'; end if;
  again := public.claim_existing_user_trial('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001');
  if again->>'reason' <> 'already_claimed' then raise exception 'repeat claim'; end if;
  if (select trial_started_at from public.workspaces where id='10000000-0000-0000-0000-000000000001') <> started
     or (select trial_expires_at from public.workspaces where id='10000000-0000-0000-0000-000000000001') <> expires
  then raise exception 'repeat extended trial'; end if;
  if (select count(*) from private.founder_trial_claims where owner_id='00000000-0000-0000-0000-000000000001') <> 1 then raise exception 'duplicate ledger'; end if;
  if (select trial_started_at from public.workspaces where id='10000000-0000-0000-0000-000000000011') is not null then raise exception 'second grant'; end if;
  if (select plan::text || '/' || billing_status::text from public.workspaces where id='10000000-0000-0000-0000-000000000001') <> 'free/none' then raise exception 'stored entitlement changed'; end if;
  if (select count(*) from public.projects where workspace_id='10000000-0000-0000-0000-000000000001') <> 1
     or (select count(*) from public.tasks where workspace_id='10000000-0000-0000-0000-000000000001') <> 1
     or (select count(*) from public.comments where workspace_id='10000000-0000-0000-0000-000000000001') <> 1
     or (select count(*) from public.catalogue_items where workspace_id='10000000-0000-0000-0000-000000000001') <> 1
     or (select count(*) from public.workspace_members where workspace_id='10000000-0000-0000-0000-000000000001') <> 2
  then raise exception 'existing workspace data changed'; end if;
end $$;

-- Confirming an earlier account makes it eligible without changing its creation date.
update auth.users set email_confirmed_at=clock_timestamp() where id='00000000-0000-0000-0000-000000000002';
do $$ begin
  if private.existing_user_trial_status('00000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002',clock_timestamp()) <> 'eligible' then raise exception 'confirmation'; end if;
end $$;
rollback;
