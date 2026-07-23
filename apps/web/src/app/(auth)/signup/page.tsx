"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, Field, GravityMark, Input } from "@/components/ui";
import { supabase } from "@/lib/supabase";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/login` },
    });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push("/dashboard");
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem 1.5rem",
      }}
    >
      <Card style={{ width: "100%", maxWidth: 400, padding: "2.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.75rem" }}>
          <GravityMark size={30} />
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "1.05rem" }}>
            Gravity OS
          </span>
        </div>
        <h1 style={{ marginBottom: "0.4rem" }}>Create your account</h1>
        <p style={{ color: "var(--muted)", marginBottom: "1.75rem" }}>Start building your creative career.</p>

        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <Field label="Email">
            <Input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              placeholder="At least 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          {error && <p style={{ color: "var(--danger)", margin: 0, fontSize: "0.85rem" }}>{error}</p>}
          <Button type="submit" disabled={loading} style={{ width: "100%", marginTop: "0.25rem" }}>
            {loading ? "Creating…" : "Create account"}
          </Button>
        </form>

        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "1.5rem", textAlign: "center" }}>
          Already have an account? <Link href="/login">Log in</Link>
        </p>
      </Card>
    </main>
  );
}
