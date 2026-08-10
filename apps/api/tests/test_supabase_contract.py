"""Static regression checks for the Supabase tenancy contract.

These run without credentials and catch accidental removal of the signup
provisioning or core RLS backstops. Live behavior is covered by
scripts/verify_supabase.py against a deployed test project.
"""
from pathlib import Path


MIGRATIONS = Path(__file__).parents[3] / "supabase" / "migrations"


def migration(name: str) -> str:
    return (MIGRATIONS / name).read_text()


def test_signup_trigger_provisions_profile_workspace_and_owner_membership():
    sql = migration("0007_auto_provision_workspace.sql")

    assert "create or replace function private.handle_new_user()" in sql.lower()
    assert "insert into public.profiles" in sql.lower()
    assert "insert into public.workspaces" in sql.lower()
    assert "insert into public.workspace_members" in sql.lower()
    assert "'owner'" in sql.lower()


def test_tenant_tables_have_member_read_and_writer_mutation_policies():
    sql = migration("0002_rls_policies.sql").lower()

    for table in ("projects", "tasks", "calendar_events", "catalogue_items", "budgets", "campaigns"):
        assert f"alter table {table}" in sql
    assert "for select using (is_workspace_member(workspace_id))" in sql
    assert "for insert with check (is_workspace_writer(workspace_id))" in sql
    assert "for delete using (is_workspace_writer(workspace_id))" in sql


def test_service_owned_outputs_are_member_read_only_under_rls():
    sql = migration("0002_rls_policies.sql").lower()

    assert "create policy gravity_select on gravity_scores" in sql
    assert "create policy ai_outputs_select on ai_outputs" in sql
    assert "create policy gravity_insert" not in sql
    assert "create policy ai_outputs_insert" not in sql


def test_invitation_acceptance_is_recipient_scoped_and_atomic():
    sql = migration("0008_workspace_invitations.sql").lower()

    assert "create table public.workspace_invitations" in sql
    assert "create or replace function public.accept_workspace_invitation" in sql
    assert "security definer" in sql
    assert "invitation.email <> lower(coalesce(auth.jwt() ->> 'email', ''))" in sql
    assert "insert into public.workspace_members" in sql
    assert "invitation.workspace_id, auth.uid(), invitation.role" in sql
    assert "set accepted_at = now()" in sql
    assert "grant execute on function public.accept_workspace_invitation(uuid) to authenticated" in sql
    assert "on conflict on constraint workspace_members_workspace_id_user_id_key" in sql


def test_collaboration_tables_are_tenant_scoped_and_activity_is_server_owned():
    sql = migration("0011_collaboration.sql").lower()

    assert "create table public.comments" in sql
    assert "create table public.workspace_activity_events" in sql
    assert "private.is_workspace_member(workspace_id)" in sql
    assert "private.is_workspace_writer(workspace_id)" in sql
    assert "author_id = auth.uid()" in sql
    assert "comments_delete_author_or_admin" in sql
    assert "revoke insert, update, delete on public.workspace_activity_events from anon, authenticated" in sql
    assert "private.validate_collaboration_target" in sql
    assert "profiles_select_shared_workspace" in sql


def test_cross_workspace_foreign_keys_have_database_guards():
    sql = migration("0013_tenant_reference_integrity.sql").lower()

    assert "prevent_workspace_reassignment" in sql
    assert "workspace_id cannot be changed" in sql
    assert "drop trigger if exists trg_%s_workspace_immutable" in sql
    assert "drop trigger if exists trg_%s_project_workspace" in sql
    for table in (
        "tasks",
        "calendar_events",
        "release_plans",
        "catalogue_items",
        "budgets",
        "campaigns",
    ):
        assert f"'{table}'" in sql
    assert "trg_%s_project_workspace" in sql
    assert "p.workspace_id = new.workspace_id" in sql
    assert "trg_content_pieces_campaign_workspace" in sql
    assert "c.workspace_id = new.workspace_id" in sql


def test_owner_membership_is_protected_even_from_service_role_mutations():
    sql = migration("0012_owner_membership_guards.sql").lower()

    assert "before insert or update on public.workspace_members" in sql
    assert "after delete on public.workspace_members" in sql
    assert "workspace owner membership cannot be deleted" in sql
    assert "workspace owner membership cannot be modified" in sql
    assert "workspace owner must have the owner role" in sql
    assert "owner role is reserved for the workspace owner" in sql


def test_security_hardening_migration_contract():
    sql = migration("0014_security_hardening.sql").lower()
    assert "drop policy if exists profiles_select_shared_workspace" in sql
    assert "sync_invitation_notification_recipient" in sql
    assert "recipient_email = null" in sql


def test_admin_plan_changes_are_atomic_and_immutable():
    sql = migration("0015_admin_plan_audit.sql").lower()

    assert "create table if not exists public.admin_plan_audit_events" in sql
    assert "before update or delete on public.admin_plan_audit_events" in sql
    assert "admin audit events are immutable" in sql
    assert "create or replace function public.admin_set_workspace_plan" in sql
    assert "for update" in sql
    assert "insert into public.admin_plan_audit_events" in sql
    assert "grant execute on function public.admin_set_workspace_plan" in sql
    assert "to service_role" in sql
    assert "create table if not exists public.admin_account_audit_events" in sql
    assert "admin_account_audit_immutable" in sql


def test_task_approval_migration_adds_review_state():
    sql = migration("0016_task_approvals.sql").lower()
    assert "alter table public.tasks" in sql
    for column in ("approval_status", "approval_submitted_by", "approval_reviewed_by", "approval_reviewed_at", "approval_note"):
        assert column in sql
    assert "create index if not exists idx_tasks_approval" in sql


def test_task_approval_integrity_is_database_enforced():
    sql = migration("0017_team_workflow_integrity.sql").lower()
    assert "approval fields are server-controlled" in sql
    assert "create or replace function public.submit_task_for_approval" in sql
    assert "create or replace function public.review_task_approval" in sql
    assert "submitter cannot review their own task" in sql
    assert "task_approval_events" in sql
    assert "drop policy if exists members_update_admin" in sql
    assert "only the workspace owner can invite administrators" in sql
    assert "notification recipient is not a workspace member" in sql


def test_task_approval_decision_atomically_completes_or_reopens_task():
    sql = migration("0018_task_approval_completion.sql").lower()
    assert "create or replace function public.review_task_approval" in sql
    assert "for update" in sql
    assert "when p_decision = 'approved' then 'done'::public.task_status" in sql
    assert "when p_decision = 'approved' then decision_at" in sql
    assert "else 'todo'::public.task_status" in sql
    assert "else null" in sql
    assert "insert into public.task_approval_events" in sql
    assert "submitter cannot review their own task" in sql
    assert "pending and approved tasks are locked" in sql
    assert "reviewed tasks cannot be deleted because approval history is immutable" in sql
    assert "before delete on public.tasks" in sql


def test_enterprise_plan_is_reserved_in_its_own_migration():
    sql = migration("0019_enterprise_plan.sql").lower()
    assert "alter type public.workspace_plan add value if not exists 'enterprise'" in sql


def test_organization_links_are_owner_opt_in_and_org_access_is_read_only():
    sql = migration("0020_enterprise_foundations.sql").lower()

    for table in ("organizations", "organization_members", "org_workspace_links"):
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql

    assert "create or replace function private.is_org_member(org uuid)" in sql
    assert "create or replace function private.has_org_workspace_read(ws uuid)" in sql
    assert "create or replace function private.can_bootstrap_org_owner(org uuid)" in sql
    assert "owner_id = auth.uid() or private.is_org_member(id)" in sql
    assert "private.can_bootstrap_org_owner(org_id)" in sql
    assert "org_workspace_links_insert_workspace_owner" in sql
    assert "linked_by = auth.uid()" in sql
    assert "array['owner']::public.member_role[]" in sql

    for table in ("workspaces", "projects", "tasks", "release_plans", "budgets", "gravity_scores"):
        assert f"create policy {table}_select_org_member" in sql
    assert "private.has_org_workspace_read(workspace_id)" in sql
    assert "projects_insert_org" not in sql
    assert "tasks_update_org" not in sql


def test_streaming_foundations_are_all_plan_member_readable_and_service_written():
    sql = migration("0020_enterprise_foundations.sql").lower()

    assert "create table public.artist_streaming_links" in sql
    assert "create table public.streaming_snapshots" in sql
    assert "streaming_snapshots_artist_workspace_fk" in sql
    assert "artist_streaming_links_select" in sql
    assert "streaming_snapshots_select" in sql
    assert "private.is_workspace_member(workspace_id)" in sql
    assert "has_workspace_plan" not in sql
    assert "workspace_plan" not in sql.split("-- soundcharts identity links", 1)[1]
    assert "revoke insert, update, delete on public.streaming_snapshots" in sql


def test_proactive_notification_preferences_are_owned_by_each_user():
    sql = migration("0021_proactive_notifications.sql").lower()

    assert "create table public.notification_preferences" in sql
    assert "alter table public.notification_preferences enable row level security" in sql
    for operation in ("select", "insert", "update", "delete"):
        assert f"notification_preferences_{operation}_own" in sql
    assert "user_id = auth.uid()" in sql
    assert "email_enabled" in sql
    assert "in_app_enabled" in sql
    assert "deadline_reminders" in sql
    assert "reminder_days_before" in sql
    assert "0 <= all(reminder_days_before)" in sql
    assert "365 >= all(reminder_days_before)" in sql


def test_plan_limits_are_enforced_at_database_boundary():
    sql = migration("0022_plan_enforcement.sql").lower()

    assert "create or replace function private.is_paid_workspace(ws uuid)" in sql
    assert "grant execute on function private.is_paid_workspace(uuid) to authenticated, service_role" in sql
    assert "create policy workspaces_insert_authed" in sql
    assert "plan = 'free'" in sql
    assert "prevent_client_plan_change" in sql
    assert "new.owner_id is distinct from old.owner_id" in sql
    assert "enforce_free_project_limit" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "free plan allows 1 active project" in sql
    assert "enforce_free_catalogue_limit" in sql
    assert "free plan allows 25 catalogue items" in sql
    for policy in (
        "release_plans_insert",
        "milestones_insert",
        "budgets_insert",
        "budget_items_insert",
        "campaigns_insert",
        "content_insert",
    ):
        assert f"create policy {policy}" in sql
    assert "private.is_paid_workspace(workspace_id)" in sql


def test_notifications_gain_safe_email_deduplication_fields():
    sql = migration("0021_proactive_notifications.sql").lower()

    assert "alter table public.notifications" in sql
    assert "add column if not exists dedupe_key text" in sql
    assert "add column if not exists emailed_at timestamptz" in sql
    assert "create unique index if not exists notifications_dedupe_key_uidx" in sql
    assert "where dedupe_key is not null" in sql


def test_email_delivery_outbox_is_retryable_idempotent_and_service_owned():
    sql = migration("0021_proactive_notifications.sql").lower()

    assert "create table public.email_deliveries" in sql
    for column in (
        "notification_id",
        "recipient_email",
        "template_key",
        "status",
        "attempts",
        "max_attempts",
        "idempotency_key",
        "next_attempt_at",
        "provider_message_id",
        "last_error",
    ):
        assert column in sql
    assert "idempotency_key       text not null unique" in sql
    assert "email_deliveries_retry_idx" in sql
    assert "attempts < max_attempts" in sql
    assert "alter table public.email_deliveries enable row level security" in sql
    assert "revoke all on public.email_deliveries from anon, authenticated" in sql
    assert "create policy email_deliveries" not in sql


def test_retention_checkins_are_service_owned_and_deduplicated():
    sql = migration("0024_retention_checkins.sql").lower()

    assert "alter table public.notification_preferences" in sql
    assert "activation_nudges boolean not null default true" in sql
    assert "weekly_digests boolean not null default true" in sql
    assert "dormant_checkins boolean not null default true" in sql
    assert "create table public.retention_checkins" in sql
    assert "dedupe_key         text not null unique" in sql
    assert "retention_checkins_user_period_uidx" in sql
    assert "revoke all on public.retention_checkins from anon, authenticated" in sql
