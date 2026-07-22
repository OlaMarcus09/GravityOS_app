"use client";

import { Card, EmptyState, OrbitMap, ProgressBar, ScoreGauge, Spinner, StatTile } from "@/components/ui";
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

  const dueToday = data?.tasks_due_today ?? [];
  const overdue = data?.tasks_overdue ?? [];
  const events = data?.upcoming_events ?? [];
  const milestones = data?.upcoming_milestones ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
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
              {score > 0 ? "Career health" : "Not yet computed"}
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

      {!isLoading && !error && (
        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: "1.5rem" }}>
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
                <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.85rem" }}>Nothing due today — clear skies.</p>
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
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1.5rem" }}>
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
