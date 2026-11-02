#!/bin/sh
set -eu
# CI's disposable database only. Two transactions race for one owner's offer.
psql -X -q -v ON_ERROR_STOP=1 <<'SQL'
insert into auth.users (id,email,created_at,email_confirmed_at) values
 ('00000000-0000-0000-0000-000000000009','race@example.com','2026-10-01','2026-10-01');
insert into public.workspaces (id,owner_id,plan,billing_status) values
 ('10000000-0000-0000-0000-000000000009','00000000-0000-0000-0000-000000000009','free','none'),
 ('10000000-0000-0000-0000-000000000099','00000000-0000-0000-0000-000000000009','free','none');
insert into public.workspace_members (workspace_id,user_id,role)
select id,owner_id,'owner' from public.workspaces where owner_id='00000000-0000-0000-0000-000000000009';
update private.existing_user_trial_campaign set enabled=true, starts_at='2000-01-01', ends_at='2100-01-01';
SQL
psql -X -q -v ON_ERROR_STOP=1 -c "begin; select public.claim_existing_user_trial('00000000-0000-0000-0000-000000000009','10000000-0000-0000-0000-000000000009'); select pg_sleep(2); commit;" >/dev/null &
first=$!
psql -X -q -v ON_ERROR_STOP=1 -c "begin; select public.claim_existing_user_trial('00000000-0000-0000-0000-000000000009','10000000-0000-0000-0000-000000000099'); commit;" >/dev/null &
second=$!
wait "$first"
wait "$second"
result=$(psql -X -A -t -v ON_ERROR_STOP=1 -c "select (select count(*) from private.founder_trial_claims where owner_id='00000000-0000-0000-0000-000000000009')::text || ',' || (select count(*) from public.workspaces where owner_id='00000000-0000-0000-0000-000000000009' and trial_started_at is not null)::text || ',' || (select extract(epoch from trial_expires_at-trial_started_at)::bigint from public.workspaces where owner_id='00000000-0000-0000-0000-000000000009' and trial_started_at is not null)::text")
test "$result" = "1,1,604800"
