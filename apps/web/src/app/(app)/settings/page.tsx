"use client";

import { useEffect, useState } from "react";

import { adminApi, type AdminWorkspace } from "@/lib/api";
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

      {/* Admin Panel — only visible to super admin */}
      {me?.user_id === "a80ea672-27f1-4ccd-be67-765e67bb65c9" && (
        <AdminPanel />
      )}
    </div>
  );
}

function AdminPanel() {
  const [email, setEmail] = useState("");
  const [results, setResults] = useState<AdminWorkspace[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const search = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const data = await adminApi.listAll(email.trim() || undefined);
      setResults(data);
      if (data.length === 0) setMsg("No workspaces found.");
    } catch (e) {
      setMsg((e as Error).message);
    }
    setLoading(false);
  };

  const changePlan = async (wsId: string, newPlan: string) => {
    setMsg(null);
    try {
      const updated = await adminApi.setPlan(wsId, newPlan);
      setResults((prev) => prev.map((w) => (w.id === wsId ? { ...w, plan: updated.plan } : w)));
      setMsg(`Updated to ${newPlan}`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  };

  return (
    <Card style={{ padding: "1.5rem", marginTop: "1.5rem" }}>
      <span className="eyebrow">Admin — Manage Plans</span>
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", alignItems: "flex-end" }}>
        <Field label="Search by email">
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="user@example.com"
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
        </Field>
        <Button onClick={search} disabled={loading} size="sm">
          {loading ? "..." : "Search"}
        </Button>
        <Button onClick={() => { setEmail(""); search(); }} variant="ghost" size="sm">
          All
        </Button>
      </div>

      {msg && <p style={{ fontSize: "0.82rem", color: "var(--accent)", margin: "0.75rem 0 0" }}>{msg}</p>}

      {results.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "1rem" }}>
          {results.map((ws) => (
            <div
              key={ws.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "0.75rem",
                padding: "0.6rem 0.75rem",
                background: "var(--surface-2)",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{ws.name}</div>
                <div style={{ fontSize: "0.72rem", color: "var(--muted-2)" }}>{ws.id.slice(0, 8)}…</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
                <Badge tone={ws.plan === "free" ? "neutral" : "accent"}>{ws.plan}</Badge>
                <select
                  value={ws.plan}
                  onChange={(e) => changePlan(ws.id, e.target.value)}
                  style={{
                    padding: "0.3rem 0.4rem",
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--fg)",
                    fontSize: "0.75rem",
                  }}
                >
                  <option value="free">Free</option>
                  <option value="pro">Pro</option>
                  <option value="team">Team</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
