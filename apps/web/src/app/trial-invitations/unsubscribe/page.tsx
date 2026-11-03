"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function TrialInvitationUnsubscribePage() {
  const [token, setToken] = useState<string | null>(null);
  const [state, setState] = useState<"ready" | "pending" | "done" | "error">("ready");

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    setToken(fragment.get("token"));
    // Keep the signed token out of browser history and copied URLs.
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function confirm() {
    if (!token || state === "pending" || state === "done") return;
    setState("pending");
    try {
      const response = await fetch(`${API_URL}/api/v1/trial-invitations/unsubscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!response.ok) throw new Error("Unsubscribe failed");
      setToken(null);
      setState("done");
    } catch {
      setState("error");
    }
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20, background: "#f6f5f1", color: "#17211d" }}>
      <section style={{ width: "100%", maxWidth: 480, padding: 32, background: "white", borderRadius: 16, border: "1px solid #e3e9e2" }}>
        <p style={{ fontWeight: 800, fontSize: 20 }}>GravityOS</p>
        <h1 style={{ fontSize: 28, marginTop: 24 }}>Trial invitation preferences</h1>
        {state === "done" ? (
          <p>You are unsubscribed from promotional trial invitations. Essential account and security messages are unaffected.</p>
        ) : token ? (
          <>
            <p>Stop receiving promotional GravityOS trial invitations at this email address?</p>
            <button type="button" onClick={confirm} disabled={state === "pending"}
              style={{ background: "#164b38", color: "white", border: 0, borderRadius: 8, padding: "14px 18px", cursor: "pointer" }}>
              {state === "pending" ? "Saving…" : "Unsubscribe"}
            </button>
            {state === "error" && <p role="alert">We could not save your preference. Please try again.</p>}
          </>
        ) : (
          <p>This unsubscribe link is missing or invalid. Please use the link in your invitation.</p>
        )}
      </section>
    </main>
  );
}
