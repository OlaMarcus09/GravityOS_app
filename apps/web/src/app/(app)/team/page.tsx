"use client";

import { useState } from "react";

import { Badge, Button, Card, EmptyState, ErrorText, Field, Input, PageHeader, Select } from "@/components/ui";
import { useInvitationMutations, useWorkspaceInvitations } from "@/lib/queries/useInvitations";
import { useTeamMemberMutations, useTeamMembers } from "@/lib/queries/useTeam";
import { useWorkspace } from "@/lib/workspace";

const roles = ["admin", "member", "viewer"] as const;

export default function TeamPage() {
  const { plan, role, workspaceId } = useWorkspace();
  const members = useTeamMembers(workspaceId);
  const memberMutations = useTeamMemberMutations(workspaceId);
  const invites = useWorkspaceInvitations(workspaceId);
  const invitationMutations = useInvitationMutations(workspaceId);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<(typeof roles)[number]>("member");
  const canManage = plan === "team" && (role === "owner" || role === "admin");

  if (plan !== "team") {
    return (
      <>
        <PageHeader title="Team" subtitle="Collaborate with managers, artists, and contributors." />
        <EmptyState title="Team workspace required" hint="Upgrade this workspace to the Team plan to invite collaborators and manage members." />
      </>
    );
  }

  const sendInvite = () => {
    invitationMutations.create.mutate({ email, role: inviteRole }, { onSuccess: () => setEmail("") });
  };

  const pendingInvites = (invites.data ?? []).filter((invite) => !invite.accepted_at && !invite.revoked_at);

  return (
    <div>
      <PageHeader title="Team" subtitle="Manage workspace members, roles, and invitations." />

      {!canManage && (
        <Card style={{ marginBottom: "1.25rem" }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>Only workspace owners and admins can manage this team. You can still view members and shared workspace data.</p>
        </Card>
      )}

      <Card style={{ marginBottom: "1.25rem" }}>
        <span className="eyebrow">Members</span>
        {members.isLoading && <p style={{ color: "var(--muted)" }}>Loading members...</p>}
        <ErrorText error={members.error} />
        <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem", marginTop: "1rem" }}>
          {(members.data ?? []).map((member) => {
            const label = member.profiles?.display_name || member.user_id.slice(0, 8);
            const isOwner = member.role === "owner";
            return (
              <div key={member.user_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", padding: "0.7rem 0", borderBottom: "1px solid var(--border)" }}>
                <div>
                  <strong>{label}</strong>
                  <p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.78rem" }}>{member.joined_at ? `Joined ${new Date(member.joined_at).toLocaleDateString()}` : "Workspace member"}</p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  {isOwner || !canManage ? (
                    <Badge tone={isOwner ? "accent" : "neutral"}>{member.role}</Badge>
                  ) : (
                    <Select value={member.role} onChange={(event) => memberMutations.update.mutate({ userId: member.user_id, role: event.target.value as (typeof roles)[number] })} style={{ width: 120 }}>
                      <option value="admin">Admin</option>
                      <option value="member">Member</option>
                      <option value="viewer">Viewer</option>
                    </Select>
                  )}
                  {canManage && !isOwner && (
                    <Button size="sm" variant="danger" onClick={() => { if (window.confirm(`Remove ${label} from this workspace?`)) memberMutations.remove.mutate(member.user_id); }}>Remove</Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <ErrorText error={memberMutations.update.error ?? memberMutations.remove.error} />
      </Card>

      <Card style={{ marginBottom: "1.25rem" }}>
        <span className="eyebrow">Invite someone</span>
        {canManage ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(180px, 1fr) 140px auto", gap: "0.7rem", marginTop: "0.9rem" }}>
              <Field label="Email"><Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="collaborator@example.com" /></Field>
              <Field label="Role"><Select value={inviteRole} onChange={(event) => setInviteRole(event.target.value as typeof inviteRole)}><option value="member">Member</option><option value="admin">Admin</option><option value="viewer">Viewer</option></Select></Field>
              <Button onClick={sendInvite} disabled={!email.trim() || invitationMutations.create.isPending} style={{ alignSelf: "end" }}>{invitationMutations.create.isPending ? "Sending..." : "Send invite"}</Button>
            </div>
            <ErrorText error={invitationMutations.create.error} />
          </>
        ) : <p style={{ color: "var(--muted)", marginBottom: 0 }}>Ask a workspace owner or admin to send invitations.</p>}
      </Card>

      <Card>
        <span className="eyebrow">Pending invitations</span>
        <ErrorText error={invites.error} />
        {pendingInvites.length === 0 && <p style={{ color: "var(--muted)", marginBottom: 0 }}>No pending invitations.</p>}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem", marginTop: "0.9rem" }}>
          {pendingInvites.map((invite) => (
            <div key={invite.id} style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
              <div><strong>{invite.email}</strong><p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.78rem" }}>{invite.role} · expires {new Date(invite.expires_at).toLocaleDateString()}</p></div>
              {canManage && <div style={{ display: "flex", gap: "0.5rem" }}><Button size="sm" variant="ghost" onClick={() => invitationMutations.resend.mutate(invite.id)}>Resend</Button><Button size="sm" variant="danger" onClick={() => invitationMutations.revoke.mutate(invite.id)}>Revoke</Button></div>}
            </div>
          ))}
        </div>
        <ErrorText error={invitationMutations.resend.error ?? invitationMutations.revoke.error} />
      </Card>
    </div>
  );
}
