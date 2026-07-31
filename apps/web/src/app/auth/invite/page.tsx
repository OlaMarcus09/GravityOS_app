"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card, Field, GravityMark, Input } from "@/components/ui";
import { invitationsApi, type WorkspaceInvitation } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function InvitePage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<WorkspaceInvitation[]>([]);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function establishSession() {
      const code = new URLSearchParams(window.location.search).get("code");
      if (code) {
        const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
        if (exchangeError) {
          setError(exchangeError.message);
          return;
        }
      }

      const { data, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !data.session) {
        setError(sessionError?.message ?? "This invitation link is invalid or has expired.");
        return;
      }
      setReady(true);
      try {
        setPending(await invitationsApi.pending());
      } catch {
        // The authenticated app can still be reached if pending invites fail to load.
      }
    }

    establishSession();
  }, []);

  async function setAccountPassword(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (updateError) {
      setError(updateError.message);
      return;
    }
    try {
      const invitations = await invitationsApi.pending();
      setPending(invitations);
      if (invitations.length === 1) {
        await acceptInvitation(invitations[0]);
      }
    } catch (acceptError) {
      setError(acceptError instanceof Error ? acceptError.message : "Your account was created, but the invitation could not be loaded.");
    }
  }

  async function acceptInvitation(invitation: WorkspaceInvitation) {
    setError(null);
    setAccepting(invitation.id);
    try {
      const result = await invitationsApi.accept(invitation.id);
      window.localStorage.setItem("gravity.workspace_id", result.workspace_id);
      router.replace("/team");
    } catch (acceptError) {
      setError(acceptError instanceof Error ? acceptError.message : "This invitation could not be accepted.");
    } finally {
      setAccepting(null);
    }
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem 1.5rem" }}>
      <Card style={{ width: "100%", maxWidth: 420, padding: "2.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.75rem" }}>
          <GravityMark size={30} />
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "1.05rem" }}>
            Gravity OS
          </span>
        </div>
        <h1 style={{ marginBottom: "0.4rem" }}>Join your workspace</h1>
        <p style={{ color: "var(--muted)", marginBottom: "1.75rem" }}>
          Set a password for your account, then join your workspace.
        </p>

        {!ready && !error && <p style={{ color: "var(--muted)" }}>Verifying invitation...</p>}

        {ready && (
          <form onSubmit={setAccountPassword} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <Field label="Password">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 6 characters"
                required
              />
            </Field>
            <Field label="Confirm password">
              <Input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
              />
            </Field>
            <Button type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Saving..." : "Continue"}
            </Button>
          </form>
        )}

        {ready && pending.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1.25rem" }}>
            <span className="eyebrow">Workspace invitations</span>
            {pending.map((invitation) => (
              <div key={invitation.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", padding: "0.8rem", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ minWidth: 0, overflowWrap: "anywhere" }}>
                  <strong>{invitation.workspaces?.name ?? "Workspace"}</strong>
                  <p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.8rem" }}>Invited as {invitation.role}</p>
                </div>
                <Button size="sm" onClick={() => acceptInvitation(invitation)} disabled={accepting !== null}>
                  {accepting === invitation.id ? "Joining..." : "Accept invitation"}
                </Button>
              </div>
            ))}
          </div>
        )}

        {error && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{error}</p>}
      </Card>
    </main>
  );
}
