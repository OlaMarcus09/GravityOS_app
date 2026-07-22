-- Gravity OS — security hardening
-- Move the RLS helper functions and the auth-signup trigger function out of
-- the PostgREST-exposed `public` schema into `private`, so they can no longer
-- be invoked as RPCs via /rest/v1/rpc/ (advisors:
-- anon/authenticated_security_definer_function_executable).
--
-- Why this works without touching the ~40 RLS policies or the auth trigger:
--   * `ALTER FUNCTION ... SET SCHEMA` preserves each function's OID, and
--     policies/triggers bind to functions by OID — so all references follow
--     the move automatically.
--   * RLS policy expressions are evaluated as the *querying* role, so
--     anon/authenticated need USAGE on `private` (EXECUTE remains via the
--     default PUBLIC grant). Revoking EXECUTE instead breaks RLS — verified.
create schema if not exists private;
grant usage on schema private to anon, authenticated, service_role;

alter function public.is_workspace_member(uuid)                      set schema private;
alter function public.has_workspace_role(uuid, public.member_role[]) set schema private;
alter function public.is_workspace_writer(uuid)                      set schema private;
alter function public.handle_new_user()                             set schema private;

-- is_workspace_writer previously called has_workspace_role unqualified via
-- search_path=public. Now that has_workspace_role lives in `private`, qualify
-- the call. CREATE OR REPLACE keeps the same OID, so dependent policies stay
-- bound.
create or replace function private.is_workspace_writer(ws uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select private.has_workspace_role(ws, array['owner','admin','member']::member_role[]);
$$;
