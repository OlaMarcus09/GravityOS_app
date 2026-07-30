"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, StatTile } from "@/components/ui";
import { adminApi, type AdminWorkspace } from "@/lib/api";
import { useMe } from "@/lib/queries/useMe";

type Plan = "free" | "pro" | "team";
type PendingPlan = { workspace: AdminWorkspace; plan: Plan } | null;

export default function AdminPage() {
  const router = useRouter();
  const { data: me, isLoading: meLoading } = useMe();
  const [workspaces, setWorkspaces] = useState<AdminWorkspace[]>([]);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingPlan, setPendingPlan] = useState<PendingPlan>(null);
  const [saving, setSaving] = useState(false);

  const loadWorkspaces = async (ownerEmail?: string) => {
    setLoading(true);
    setError(null);
    try {
      setWorkspaces(await adminApi.listAll(ownerEmail));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!meLoading && me && !me.capabilities.platform_admin) router.replace("/dashboard");
  }, [me, meLoading, router]);

  useEffect(() => {
    if (me?.capabilities.platform_admin) void loadWorkspaces();
  }, [me?.capabilities.platform_admin]);

  const metrics = useMemo(() => ({
    total: workspaces.length,
    free: workspaces.filter((workspace) => workspace.plan === "free").length,
    paid: workspaces.filter((workspace) => workspace.plan !== "free").length,
    members: workspaces.reduce((total, workspace) => total + (workspace.workspace_members?.length ?? 0), 0),
  }), [workspaces]);

  const search = () => void loadWorkspaces(email.trim() || undefined);
  const clearSearch = () => {
    setEmail("");
    void loadWorkspaces();
  };

  const confirmPlanChange = async () => {
    if (!pendingPlan) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await adminApi.setPlan(pendingPlan.workspace.id, pendingPlan.plan);
      setWorkspaces((current) => current.map((workspace) => (
        workspace.id === updated.id ? { ...workspace, plan: updated.plan } : workspace
      )));
      setNotice(`${pendingPlan.workspace.name} is now on the ${pendingPlan.plan} plan.`);
      setPendingPlan(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (meLoading || !me?.capabilities.platform_admin) return <Spinner label="Checking admin access..." />;

  return (
    <div>
      <PageHeader title="Platform Admin" subtitle="Manage Gravity OS workspaces and subscription access." />

      <div className="admin-metrics">
        <Card><StatTile label="Workspaces" value={metrics.total} tone="cyan" /></Card>
        <Card><StatTile label="Free" value={metrics.free} /></Card>
        <Card><StatTile label="Pro + Team" value={metrics.paid} tone="accent" /></Card>
        <Card><StatTile label="Members" value={metrics.members} tone="success" /></Card>
      </div>

      <Card style={{ marginTop: "1.25rem", padding: "1.25rem" }}>
        <div className="admin-toolbar">
          <div>
            <span className="eyebrow">Workspace directory</span>
            <p style={{ color: "var(--muted)", margin: "0.35rem 0 0" }}>
              Search by the workspace owner&apos;s exact email address.
            </p>
          </div>
          <div className="admin-search">
            <Input
              aria-label="Owner email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && search()}
              placeholder="owner@example.com"
            />
            <Button onClick={search} disabled={loading}>Search</Button>
            <Button onClick={clearSearch} disabled={loading} variant="ghost">Show all</Button>
          </div>
        </div>

        {notice && <p className="admin-notice">{notice}</p>}
        {error && <p className="admin-error">{error}</p>}
        {loading && <Spinner label="Loading workspaces..." />}

        {!loading && workspaces.length === 0 && (
          <EmptyState title="No workspaces found" hint="Try another owner email or show all workspaces." />
        )}

        {!loading && workspaces.length > 0 && (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Workspace</th>
                  <th>Type</th>
                  <th>Members</th>
                  <th>Created</th>
                  <th>Plan</th>
                </tr>
              </thead>
              <tbody>
                {workspaces.map((workspace) => (
                  <tr key={workspace.id}>
                    <td>
                      <strong>{workspace.name}</strong>
                      <span>{workspace.id}</span>
                    </td>
                    <td><Badge>{workspace.type}</Badge></td>
                    <td>{workspace.workspace_members?.length ?? 0}</td>
                    <td>{new Date(workspace.created_at).toLocaleDateString()}</td>
                    <td>
                      <Select
                        aria-label={`Plan for ${workspace.name}`}
                        value={workspace.plan}
                        onChange={(event) => setPendingPlan({ workspace, plan: event.target.value as Plan })}
                        style={{ minWidth: 105 }}
                      >
                        <option value="free">Free</option>
                        <option value="pro">Pro</option>
                        <option value="team">Team</option>
                      </Select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={Boolean(pendingPlan)} onClose={() => !saving && setPendingPlan(null)} title="Confirm plan change">
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Change <strong style={{ color: "var(--fg)" }}>{pendingPlan?.workspace.name}</strong> from {pendingPlan?.workspace.plan} to {pendingPlan?.plan}?
          This immediately changes the features available to every workspace member.
        </p>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
          <Button variant="ghost" onClick={() => setPendingPlan(null)} disabled={saving}>Cancel</Button>
          <Button onClick={confirmPlanChange} disabled={saving}>{saving ? "Updating..." : "Confirm change"}</Button>
        </div>
      </Modal>
    </div>
  );
}
