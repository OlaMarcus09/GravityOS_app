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
