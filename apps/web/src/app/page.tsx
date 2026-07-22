import Link from "next/link";

import { Button, GravityMark } from "@/components/ui";

// Public landing — the brand's first impression. Space-themed hero over the
// global starfield/nebula backdrop (globals.css), with the Gravity mark.
export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "4rem 1.5rem",
        textAlign: "center",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "2.5rem" }}>
        <GravityMark size={38} />
        <span style={{ fontFamily: "var(--font-display)", fontSize: "1.15rem", fontWeight: 600, letterSpacing: "-0.01em" }}>
          Gravity OS
        </span>
      </div>

      <p className="eyebrow" style={{ marginBottom: "1rem" }}>
        The operating system for creative careers
      </p>
      <h1
        style={{
          fontSize: "clamp(2.4rem, 6vw, 4rem)",
          lineHeight: 1.05,
          maxWidth: 720,
          marginBottom: "1.25rem",
        }}
      >
        Build your creative career{" "}
        <span
          style={{
            background: "linear-gradient(120deg, var(--accent), var(--cyan))",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          in orbit
        </span>
      </h1>
      <p style={{ color: "var(--muted)", fontSize: "1.05rem", maxWidth: 520, marginBottom: "2.5rem" }}>
        Plan releases, organize your catalogue, manage budgets, and stay consistent —
        all from one intelligent mission control.
      </p>

      <div style={{ display: "flex", gap: "0.85rem", flexWrap: "wrap", justifyContent: "center" }}>
        <Link href="/signup">
          <Button size="md">Get started</Button>
        </Link>
        <Link href="/login">
          <Button variant="ghost" size="md">
            Log in
          </Button>
        </Link>
      </div>
    </main>
  );
}
