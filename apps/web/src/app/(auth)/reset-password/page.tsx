"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Card, Field, GravityMark, Input } from "@/components/ui";
import { supabase } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [ready, setReady] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY" && session) {
        setReady(true);
        setChecking(false);
      }
    });
    // The auth client processes recovery links and emits PASSWORD_RECOVERY.
    // An ordinary signed-in session alone cannot open this form.
    const timeout = window.setTimeout(() => setChecking(false), 12000);
    return () => { subscription.unsubscribe(); window.clearTimeout(timeout); };
  }, []);

  async function updatePassword(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || loading || saved) return;
    if (password.length < 8) {
      setError("Use at least 8 characters for your new password.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    setError(null);
    const { data, error: userError } = await supabase.auth.getUser();
    if (userError || !data.user) {
      setError("This reset link has expired. Request a new one.");
      setReady(false);
      setLoading(false);
      return;
    }
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (updateError) {
      setError("We couldn't update your password. Please request a new link and try again.");
      return;
    }
    setSaved(true);
    setPassword("");
    setConfirmation("");
    await supabase.auth.signOut();
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem 1.5rem" }}>
      <Card style={{ width: "100%", maxWidth: 420, padding: "2.25rem" }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem", color: "var(--fg)", marginBottom: "1.75rem", fontFamily: "var(--font-display)", fontWeight: 600 }}>
          <GravityMark size={30} /> GravityOS
        </Link>
        <h1 style={{ marginBottom: "0.5rem" }}>Choose a new password</h1>
        {saved ? (
          <div role="status"><p style={{ color: "var(--success)", lineHeight: 1.6 }}>Your password has been updated. You can now log in with your new password.</p><Link href="/login"><Button style={{ width: "100%" }}>Go to login</Button></Link></div>
        ) : ready ? (
          <form onSubmit={updatePassword} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <p style={{ color: "var(--muted)", margin: 0 }}>Use a password you haven&apos;t used before.</p>
            <Field label="New password"><Input type="password" autoComplete="new-password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
            <Field label="Confirm new password"><Input type="password" autoComplete="new-password" minLength={8} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required /></Field>
            {error && <p role="alert" style={{ color: "var(--danger)", margin: 0 }}>{error}</p>}
            <Button type="submit" disabled={loading} style={{ width: "100%" }}>{loading ? "Saving…" : "Save new password"}</Button>
          </form>
        ) : (
          <div role="status"><p style={{ color: "var(--muted)", lineHeight: 1.6 }}>{checking ? "Checking your reset link…" : "This reset link is invalid or has expired."}</p>{!checking && <Link href="/forgot-password">Request a new link</Link>}</div>
        )}
      </Card>
    </main>
  );
}
