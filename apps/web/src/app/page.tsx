import Link from "next/link";

import { Button, GravityMark } from "@/components/ui";

const TIERS = [
  {
    name: "Free",
    price: "N0",
    period: "forever",
    description: "Get started and plan your first release.",
    features: [
      "1 active project",
      "25 catalogue items",
      "Tasks + Calendar",
      "Basic dashboard",
    ],
    cta: "Get started",
    href: "/signup",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "Coming soon",
    period: "",
    description: "Unlimited tools for the working creative.",
    features: [
      "Unlimited projects",
      "Unlimited catalogue",
      "Release planner",
      "Budget planner",
      "Marketing planner",
      "Gravity Score",
      "AI Manager",
    ],
    cta: "Join waitlist",
    href: "/signup",
    highlighted: true,
  },
  {
    name: "Team",
    price: "Coming soon",
    period: "",
    description: "For managers, labels, and creative agencies.",
    features: [
      "Everything in Pro",
      "Multiple workspaces",
      "Team permissions",
      "Shared calendars",
      "Approval workflows",
    ],
    cta: "Join waitlist",
    href: "/signup",
    highlighted: false,
  },
];

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
        padding: "4rem 1.5rem",
      }}
    >
      {/* Hero */}
      <section
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          minHeight: "70vh",
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
      </section>

      {/* Pricing */}
      <section
        id="pricing"
        style={{
          width: "100%",
          maxWidth: 960,
          padding: "4rem 0 2rem",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <p className="eyebrow" style={{ marginBottom: "0.75rem" }}>Pricing</p>
          <h2 style={{ fontSize: "clamp(1.6rem, 4vw, 2.2rem)", margin: 0 }}>
            Simple plans for every stage
          </h2>
          <p style={{ color: "var(--muted)", marginTop: "0.6rem", maxWidth: 480, marginLeft: "auto", marginRight: "auto" }}>
            Start free. Upgrade when you need more power.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "1.25rem",
          }}
        >
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className="glass"
              style={{
                padding: "1.75rem 1.5rem",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
                border: tier.highlighted
                  ? "1px solid var(--accent)"
                  : "1px solid var(--border)",
                boxShadow: tier.highlighted ? "var(--glow-accent)" : "var(--shadow)",
                position: "relative",
              }}
            >
              {tier.highlighted && (
                <span
                  style={{
                    position: "absolute",
                    top: "-0.65rem",
                    left: "50%",
                    transform: "translateX(-50%)",
                    background: "linear-gradient(180deg, var(--accent-hover), var(--accent))",
                    color: "#1a1205",
                    fontSize: "0.68rem",
                    fontWeight: 700,
                    padding: "0.2rem 0.75rem",
                    borderRadius: 999,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  Most popular
                </span>
              )}

              <div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.15rem", fontWeight: 600, margin: 0 }}>
                  {tier.name}
                </h3>
                <p style={{ color: "var(--muted)", fontSize: "0.82rem", margin: "0.25rem 0 0" }}>
                  {tier.description}
                </p>
              </div>

              <div style={{ display: "flex", alignItems: "baseline", gap: "0.3rem" }}>
                <span style={{ fontFamily: "var(--font-display)", fontSize: "1.75rem", fontWeight: 600 }}>
                  {tier.price}
                </span>
                {tier.period && (
                  <span style={{ color: "var(--muted)", fontSize: "0.82rem" }}>/{tier.period}</span>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", flex: 1 }}>
                {tier.features.map((f) => (
                  <div key={f} style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem" }}>
                    <span style={{ color: "var(--success)", fontWeight: 700, flexShrink: 0 }}>+</span>
                    <span>{f}</span>
                  </div>
                ))}
              </div>

              <Link href={tier.href}>
                <Button
                  variant={tier.highlighted ? "primary" : "ghost"}
                  style={{ width: "100%", marginTop: "0.5rem" }}
                >
                  {tier.cta}
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
