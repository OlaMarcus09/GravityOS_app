"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Card, Field, GravityMark, Input } from "@/components/ui";
import { supabase } from "@/lib/supabase";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function requestReset(event: React.FormEvent) {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setLoading(false);
    if (resetError) {
      setError("We couldn't send a reset link right now. Please try again later.");
      return;
    }
    setSent(true);
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem 1.5rem" }}>
      <Card style={{ width: "100%", maxWidth: 420, padding: "2.25rem" }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem", color: "var(--fg)", marginBottom: "1.75rem", fontFamily: "var(--font-display)", fontWeight: 600 }}>
          <GravityMark size={30} /> GravityOS
        </Link>
        <h1 style={{ marginBottom: "0.5rem" }}>Reset your password</h1>
        <p style={{ color: "var(--muted)", marginBottom: "1.75rem" }}>Enter your account email and we&apos;ll send a secure reset link.</p>
        {sent ? (
          <p role="status" style={{ color: "var(--success)", lineHeight: 1.6 }}>
            If an account uses that address, a reset link is on its way. Check your inbox and spam folder.
          </p>
        ) : (
          <form onSubmit={requestReset} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <Field label="Email">
              <Input type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </Field>
            {error && <p role="alert" style={{ color: "var(--danger)", margin: 0 }}>{error}</p>}
            <Button type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Sending…" : "Send reset link"}
            </Button>
          </form>
        )}
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "1.5rem", textAlign: "center" }}>
          Remembered it? <Link href="/login">Back to login</Link>
        </p>
      </Card>
    </main>
  );
}
