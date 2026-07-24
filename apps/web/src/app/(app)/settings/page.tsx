"use client";

import Link from "next/link";

import { useMe } from "@/lib/queries/useMe";
import { useWorkspace } from "@/lib/workspace";
import { Badge, Button, Card, PageHeader } from "@/components/ui";

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
  const { plan } = useWorkspace();

  const current = PLAN_FEATURES[plan] ?? PLAN_FEATURES.free;

  return (
    <div>
      <PageHeader title="Settings" subtitle="Manage your profile and plan." />

      {/* Profile */}
      <Card style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <span className="eyebrow">Profile</span>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
          <Row label="Display name" value={me?.profile?.display_name ?? "—"} />
          <Row label="Email" value={me?.email ?? "—"} />
          <Row label="Creative role" value={me?.profile?.creative_role ?? "—"} />
        </div>
      </Card>

      {/* Plan & Billing */}
      <Card style={{ padding: "1.5rem" }}>
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
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", fontSize: "0.85rem" }}>
      <span style={{ color: "var(--muted)", fontWeight: 550 }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}
