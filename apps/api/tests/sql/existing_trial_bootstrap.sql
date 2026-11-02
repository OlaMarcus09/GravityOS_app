-- Minimal isolated schema for CI. Never run against a Supabase project.
create role anon;
create role authenticated;
create role service_role;
create schema auth;
create schema private;
create schema extensions;
create extension pgcrypto with schema extensions;
create type public.workspace_plan as enum ('free','pro','team','enterprise');
create type public.workspace_billing_status as enum ('none','manual','active','expired');
create type public.member_role as enum ('owner','admin','member','viewer');
create table auth.users (
 id uuid primary key,
 email text,
 created_at timestamptz not null,
 email_confirmed_at timestamptz
);
create table public.workspaces (
 id uuid primary key,
 owner_id uuid not null,
 plan public.workspace_plan not null default 'free',
 billing_status public.workspace_billing_status not null default 'none',
 current_period_end timestamptz,
 trial_started_at timestamptz,
 trial_expires_at timestamptz,
 constraint workspaces_trial_period_exact check (
 (trial_started_at is null and trial_expires_at is null)
 or (trial_started_at is not null and trial_expires_at = trial_started_at + interval '168 hours'))
);
create table public.workspace_members (
 workspace_id uuid not null,
 user_id uuid not null,
 role public.member_role not null
);
create table private.founder_trial_claims (
 owner_id uuid primary key,
 email_digest bytea not null unique,
 workspace_id uuid not null unique,
 claimed_at timestamptz not null
);
create table public.projects (workspace_id uuid not null);
create table public.tasks (workspace_id uuid not null);
create table public.comments (workspace_id uuid not null);
create table public.catalogue_items (workspace_id uuid not null);
