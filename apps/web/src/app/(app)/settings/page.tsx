"use client";

import { useEffect, useState } from "react";

import { useMe, useProfileMutation } from "@/lib/queries/useMe";
import { useInvitationMutations, usePendingInvitations, useWorkspaceInvitations } from "@/lib/queries/useInvitations";
import { useWorkspace } from "@/lib/workspace";
import { Badge, Button, Card, ErrorText, Field, Input, PageHeader, Select } from "@/components/ui";

const CREATIVE_ROLES = [
  "artist",
  "producer",
  "songwriter",
  "engineer",
  "manager",
  "designer",
  "videographer",
  "dj",
  "other",
] as const;

const PLAN_FEATURES: Record<string, { label: string; features: string[] }> = {
  free: {
    label: "Free",
    features: [
      "1 active project",
      "25 catalogue items",
      "Tasks + Calendar",
      "Basic dashboard",
    ],
  },
  pro: {
    label: "Pro",
    features: [
      "Unlimited projects",
      "Unlimited catalogue",
      "Release planner",
      "Budget planner",
      "Marketing planner",
      "Gravity Score",
      "AI Manager",
    ],
  },
  team: {
    label: "Team",
    features: [
      "Everything in Pro",
      "Multiple workspaces",
      "Team permissions",
      "Shared calendars",
      "Approval workflows",
    ],
  },
};

export default function SettingsPage() {
  const { data: me } = useMe();
  const { plan, role, workspaceId, setWorkspaceId } = useWorkspace();
  const mutation = useProfileMutation();

  const [displayName, setDisplayName] = useState("");
  const [creativeRole, setCreativeRole] = useState("");
  const [timezone, setTimezone] = useState("");
  const [saved, setSaved] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member" | "viewer">("member");
  const pending = usePendingInvitations();
  const workspaceInvites = useWorkspaceInvitations(workspaceId);
  const invitations = useInvitationMutations(workspaceId);

  // Seed form from server data
  useEffect(() => {
    if (me?.profile) {
      setDisplayName(me.profile.display_name ?? "");
      setCreativeRole(me.profile.creative_role ?? "");
      setTimezone(me.profile.timezone ?? "");
    }
  }, [me?.profile]);

  const dirty =
    displayName !== (me?.profile?.display_name ?? "") ||
    creativeRole !== (me?.profile?.creative_role ?? "") ||
    timezone !== (me?.profile?.timezone ?? "");

  const save = () => {
    setSaved(false);
    mutation.mutate(
      {
        display_name: displayName.trim() || undefined,
        creative_role: creativeRole || undefined,
        timezone: timezone || undefined,
      },
      { onSuccess: () => setSaved(true) },
    );
  };

  const current = PLAN_FEATURES[plan] ?? PLAN_FEATURES.free;
  const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const canManageTeam = plan === "team" && (role === "owner" || role === "admin");

  const sendInvite = () => {
    invitations.create.mutate(
      { email: inviteEmail, role: inviteRole },
      { onSuccess: () => setInviteEmail("") },
    );
  };

  return (
    <div>
      <PageHeader title="Settings" subtitle="Manage your profile and plan." />

      {pending.data && pending.data.length > 0 && (
        <Card style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
          <span className="eyebrow">Workspace invitations</span>
          {pending.data.map((invite) => (
            <div key={invite.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", marginTop: "0.9rem", flexWrap: "wrap" }}>
              <div>
                <strong>{invite.workspaces?.name ?? "Workspace"}</strong>
                <p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.82rem" }}>Invited as {invite.role}</p>
              </div>
              <Button size="sm" disabled={invitations.accept.isPending} onClick={() => invitations.accept.mutate(invite.id, { onSuccess: (result) => setWorkspaceId(result.workspace_id) })}>Accept</Button>
            </div>
          ))}
          <ErrorText error={invitations.accept.error} />
        </Card>
      )}

      {/* Profile */}
      <Card style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <span className="eyebrow">Profile</span>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
          <Field label="Email">
            <Input value={me?.email ?? ""} disabled />
          </Field>
          <Field label="Display name">
            <Input
              value={displayName}
              onChange={(e) => { setDisplayName(e.target.value); setSaved(false); }}
              placeholder="Your name"
            />
          </Field>
          <Field label="Creative role">
            <Select
              value={creativeRole}
              onChange={(e) => { setCreativeRole(e.target.value); setSaved(false); }}
            >
              <option value="">Select a role</option>
              {CREATIVE_ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </Select>
          </Field>
          <Field label="Timezone">
            <Input
              value={timezone}
              onChange={(e) => { setTimezone(e.target.value); setSaved(false); }}
              placeholder={userTz}
            />
          </Field>
          <ErrorText error={mutation.error} />
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <Button onClick={save} disabled={!dirty || mutation.isPending}>
              {mutation.isPending ? "Saving..." : "Save changes"}
            </Button>
            {saved && <span style={{ fontSize: "0.82rem", color: "var(--success)" }}>Saved</span>}
          </div>
        </div>
      </Card>

      {/* Plan & Billing */}
      <Card style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
          <span className="eyebrow">Plan & Billing</span>
          <Badge tone={plan === "free" ? "neutral" : "accent"}>{current.label}</Badge>
        </div>

        <p style={{ color: "var(--muted)", fontSize: "0.85rem", margin: "0 0 1rem" }}>
          {plan === "free"
            ? "You're on the Free plan. Upgrade to unlock release planning, budgets, marketing, and more."
            : `You're on the ${current.label} plan with full access to all features.`}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginBottom: "1.25rem" }}>
          {current.features.map((f) => (
            <div key={f} style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem" }}>
              <span style={{ color: "var(--success)", fontWeight: 700 }}>+</span>
              <span>{f}</span>
            </div>
          ))}
        </div>

        {plan === "free" && (
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <Button>Upgrade to Pro</Button>
            <Button variant="ghost">Compare plans</Button>
          </div>
        )}

        {plan !== "free" && (
          <p style={{ color: "var(--muted-2)", fontSize: "0.8rem", margin: 0 }}>
            Billing management will be available once Stripe is connected.
          </p>
        )}
      </Card>

      <Card style={{ padding: "1.5rem" }}>
        <span className="eyebrow">Team</span>
        {!canManageTeam ? (
          <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginBottom: 0 }}>
            {plan !== "team" ? "Email invitations are available on the Team plan." : "Only workspace owners and admins can manage invitations."}
          </p>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(180px, 1fr) 140px auto", gap: "0.75rem", marginTop: "0.9rem" }}>
              <Input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="collaborator@example.com" />
              <Select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}>
                <option value="member">Member</option><option value="admin">Admin</option><option value="viewer">Viewer</option>
              </Select>
              <Button onClick={sendInvite} disabled={!inviteEmail.trim() || invitations.create.isPending}>{invitations.create.isPending ? "Sending..." : "Invite"}</Button>
            </div>
            <ErrorText error={invitations.create.error} />
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1rem" }}>
              {(workspaceInvites.data ?? []).filter((invite) => !invite.accepted_at && !invite.revoked_at).map((invite) => (
                <div key={invite.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                  <div><strong style={{ fontSize: "0.88rem" }}>{invite.email}</strong><p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.78rem" }}>{invite.role} · expires {new Date(invite.expires_at).toLocaleDateString()}</p></div>
                  <div style={{ display: "flex", gap: "0.5rem" }}><Button size="sm" variant="ghost" onClick={() => invitations.resend.mutate(invite.id)}>Resend</Button><Button size="sm" variant="danger" onClick={() => invitations.revoke.mutate(invite.id)}>Revoke</Button></div>
                </div>
              ))}
            </div>
            <ErrorText error={workspaceInvites.error ?? invitations.resend.error ?? invitations.revoke.error} />
          </>
        )}
      </Card>

    </div>
  );
}
