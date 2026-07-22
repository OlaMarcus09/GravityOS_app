"use client";

import Link from "next/link";

import { Button, Card, EmptyState, OrbitMap, ScoreGauge, Spinner, StatTile } from "@/components/ui";
import { useDashboard } from "@/lib/queries/useDashboard";
import { useMe } from "@/lib/queries/useMe";

// Dashboard — "Mission Control". Aggregates the day's priorities, the Gravity
// Score, an orbital view of the active release stages, and upcoming items.
// Every section degrades to an empty state so a fresh workspace still looks intentional.

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

// Static orbit stages (release lifecycle from the PRD). Tones hint progress;
// once a release plan is selected we can drive these from real milestones.
const ORBIT_STAGES = [
  { label: "Record", tone: "accent" as const },
  { label: "Mix", tone: "cyan" as const },
  { label: "Master", tone: "violet" as const },
  { label: "Artwork", tone: "muted" as const },
  { label: "Upload", tone: "muted" as const },
  { label: "Press", tone: "muted" as const },
];

export default function DashboardPage() {
  const { data: me } = useMe();
  const { data, isLoading, error } = useDashboard();

  const name = me?.profile?.display_name?.split(" ")[0] ?? "there";
  const score = data?.gravity_score?.score ?? 0;

  const projectCount = data?.project_count ?? 0;
  const taskCount = data?.task_count ?? 0;
  const catalogueCount = data?.catalogue_count ?? 0;
  const hasReleasePlan = data?.has_release_plan ?? false;

  const checklistSteps = [
    { label: "Create your first project", href: "/projects", done: projectCount > 0 },
    { label: "Add a task", href: "/tasks", done: taskCount > 0 },
    { label: "Plan a release", href: "/projects", done: hasReleasePlan },
    { label: "Upload something to your Vault", href: "/catalogue", done: catalogueCount > 0 },
  ];
  const allDone = checklistSteps.every((s) => s.done);

  const dueToday = data?.tasks_due_today ?? [];
  const overdue = data?.tasks_overdue ?? [];
  const events = data?.upcoming_events ?? [];
  const milestones = data?.upcoming_milestones ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <span className="eyebrow">Mission Control</span>
          <h1 style={{ marginTop: "0.3rem" }}>
            {greeting()}, {name} <span style={{ fontSize: "1.3rem" }}>👋</span>
          </h1>
          <p style={{ color: "var(--muted)", margin: "0.25rem 0 0" }}>Let&apos;s keep the momentum.</p>
        </div>
        <Card style={{ display: "flex", alignItems: "center", gap: "0.85rem", padding: "0.85rem 1.1rem" }}>
          <ScoreGauge score={score} label="SCORE" />
          <div>
            <div className="eyebrow">Gravity Score</div>
            <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginTop: "0.2rem" }}>
              {score > 0 ? "Career health" : "Create a project to start your score"}
            </div>
          </div>
        </Card>
      </div>

      {error && <Card style={{ color: "var(--danger)" }}>API error: {(error as Error).message}</Card>}
      {isLoading && (
        <Card>
          <Spinner label="Loading your orbit…" />
        </Card>
      )}

      {!isLoading && !error && !allDone && (
        <Card style={{ padding: "1.25rem 1.4rem" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <div>
              <span className="eyebrow">Getting started</span>
              <h2 style={{ marginTop: "0.35rem" }}>Launch checklist</h2>
            </div>
            <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
              {checklistSteps.filter((s) => s.done).length} of {checklistSteps.length} done
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {checklistSteps.map((step) => (
              <div
                key={step.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.6rem 0.75rem",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                }}
              >
                <span
                  style={{
                    width: 22,
                    height: 22,
                    flexShrink: 0,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    color: step.done ? "#1a1205" : "var(--muted-2)",
                    background: step.done ? "var(--success)" : "transparent",
                    border: step.done ? "none" : "1.5px solid var(--border-strong)",
                    boxShadow: step.done ? "0 0 8px var(--success)" : "none",
                  }}
                >
                  {step.done ? "✓" : ""}
                </span>
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    fontSize: "0.9rem",
                    color: step.done ? "var(--muted)" : "var(--fg)",
                    textDecoration: step.done ? "line-through" : "none",
                  }}
                >
                  {step.label}
                </span>
                {!step.done && (
                  <Link href={step.href}>
                    <Button size="sm">Start</Button>
                  </Link>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {!isLoading && !error && (
        <div className="split-2" style={{ gap: "1.5rem" }}>
          {/* Active Orbit */}
          <Card style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <span className="eyebrow">Active Orbit</span>
                <h2 style={{ marginTop: "0.35rem" }}>Release lifecycle</h2>
              </div>
              <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{milestones.length} upcoming</span>
            </div>
            <OrbitMap nodes={ORBIT_STAGES} size={280} />
          </Card>

          {/* Right column */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Today's Pull */}
            <Card>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.9rem" }}>
                <span className="eyebrow">Today&apos;s Pull</span>
                <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{dueToday.length} due</span>
              </div>
              {dueToday.length === 0 && overdue.length === 0 ? (
                projectCount === 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "0.75rem" }}>
                    <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.85rem" }}>
                      Nothing to show yet — create your first project to get started.
                    </p>
                    <Link href="/projects">
                      <Button size="sm">Create a project</Button>
                    </Link>
                  </div>
                ) : (
                  <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.85rem" }}>Clear skies — nothing due today.</p>
                )
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                  {overdue.slice(0, 3).map((t) => (
                    <TaskLine key={t.id} title={t.title} tag="Overdue" tone="var(--danger)" />
                  ))}
                  {dueToday.slice(0, 4).map((t) => (
                    <TaskLine key={t.id} title={t.title} tag={t.priority} tone="var(--accent)" />
                  ))}
                </div>
              )}
            </Card>

            {/* Upcoming */}
            <Card>
              <span className="eyebrow">Upcoming</span>
              <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                {events.length === 0 && milestones.length === 0 ? (
                  <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.85rem" }}>No events on the horizon.</p>
                ) : (
                  <>
                    {events.slice(0, 3).map((e) => (
                      <FeedLine key={e.id} title={e.title} sub={new Date(e.starts_at).toLocaleDateString()} tone="var(--cyan)" />
                    ))}
                    {milestones.slice(0, 3).map((m) => (
                      <FeedLine
                        key={m.id}
                        title={m.title}
                        sub={m.due_date ? new Date(m.due_date).toLocaleDateString() : m.category}
                        tone="var(--violet)"
                      />
                    ))}
                  </>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Stat row */}
      {!isLoading && !error && (
        <div className="stat-grid" style={{ gap: "1.5rem" }}>
          <Card>
            <StatTile label="Due Today" value={dueToday.length} tone={dueToday.length ? "accent" : undefined} />
          </Card>
          <Card>
            <StatTile label="Overdue" value={overdue.length} tone={overdue.length ? "danger" : undefined} />
          </Card>
          <Card>
            <StatTile label="Upcoming Events" value={events.length} tone="cyan" />
          </Card>
          <Card>
            <StatTile label="Milestones" value={milestones.length} tone="success" />
          </Card>
        </div>
      )}

      {!isLoading && !error && !data?.gravity_score && dueToday.length === 0 && events.length === 0 && (
        <EmptyState
          title="Your workspace is just getting started"
          hint="Create a project and a release plan to see your orbit come alive."
        />
      )}
    </div>
  );
}

function TaskLine({ title, tag, tone }: { title: string; tag: string; tone: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.55rem", minWidth: 0 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: tone, boxShadow: `0 0 6px ${tone}`, flexShrink: 0 }} />
        <span style={{ fontSize: "0.85rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</span>
      </div>
      <span style={{ fontSize: "0.68rem", color: tone, textTransform: "capitalize", flexShrink: 0 }}>{tag}</span>
    </div>
  );
}

function FeedLine({ title, sub, tone }: { title: string; sub: string; tone: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: tone, boxShadow: `0 0 6px ${tone}`, flexShrink: 0 }} />
      <span style={{ fontSize: "0.85rem", flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</span>
      <span style={{ fontSize: "0.72rem", color: "var(--muted-2)", flexShrink: 0 }}>{sub}</span>
    </div>
  );
}
