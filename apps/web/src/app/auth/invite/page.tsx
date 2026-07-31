"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card, Field, GravityMark, Input } from "@/components/ui";
import { supabase } from "@/lib/supabase";

export default function InvitePage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
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
    router.replace("/settings");
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
          Set a password for your account, then accept the workspace invitation in Settings.
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

        {error && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{error}</p>}
      </Card>
    </main>
  );
}
