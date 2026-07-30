"use client";

import { useEffect, useState } from "react";

import { useMe, useProfileMutation } from "@/lib/queries/useMe";
import { useWorkspace } from "@/lib/workspace";
import { Badge, Button, Card, ErrorText, Field, Input, PageHeader, Select } from "@/components/ui";

const CREATIVE_ROLES = [
  "artist",
  "producer",
  "songwriter",
  "engineer",
  "manager",
  "designer",
  "videographer",
  "dj",
  "other",
] as const;

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
  const mutation = useProfileMutation();

  const [displayName, setDisplayName] = useState("");
  const [creativeRole, setCreativeRole] = useState("");
  const [timezone, setTimezone] = useState("");
  const [saved, setSaved] = useState(false);

  // Seed form from server data
  useEffect(() => {
    if (me?.profile) {
      setDisplayName(me.profile.display_name ?? "");
      setCreativeRole(me.profile.creative_role ?? "");
      setTimezone(me.profile.timezone ?? "");
    }
  }, [me?.profile]);

  const dirty =
    displayName !== (me?.profile?.display_name ?? "") ||
    creativeRole !== (me?.profile?.creative_role ?? "") ||
    timezone !== (me?.profile?.timezone ?? "");

  const save = () => {
    setSaved(false);
    mutation.mutate(
      {
        display_name: displayName.trim() || undefined,
        creative_role: creativeRole || undefined,
        timezone: timezone || undefined,
      },
      { onSuccess: () => setSaved(true) },
    );
  };

  const current = PLAN_FEATURES[plan] ?? PLAN_FEATURES.free;
  const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <div>
      <PageHeader title="Settings" subtitle="Manage your profile and plan." />

      {/* Profile */}
      <Card style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <span className="eyebrow">Profile</span>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
          <Field label="Email">
            <Input value={me?.email ?? ""} disabled />
          </Field>
          <Field label="Display name">
            <Input
              value={displayName}
              onChange={(e) => { setDisplayName(e.target.value); setSaved(false); }}
              placeholder="Your name"
            />
          </Field>
          <Field label="Creative role">
            <Select
              value={creativeRole}
              onChange={(e) => { setCreativeRole(e.target.value); setSaved(false); }}
            >
              <option value="">Select a role</option>
              {CREATIVE_ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </Select>
          </Field>
          <Field label="Timezone">
            <Input
              value={timezone}
              onChange={(e) => { setTimezone(e.target.value); setSaved(false); }}
              placeholder={userTz}
            />
          </Field>
          <ErrorText error={mutation.error} />
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <Button onClick={save} disabled={!dirty || mutation.isPending}>
              {mutation.isPending ? "Saving..." : "Save changes"}
            </Button>
            {saved && <span style={{ fontSize: "0.82rem", color: "var(--success)" }}>Saved</span>}
          </div>
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
