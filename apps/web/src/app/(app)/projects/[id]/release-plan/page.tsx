"use client";

import Link from "next/link";
import { useState } from "react";

import type { Milestone, MilestoneInput, ReleasePlan } from "@/lib/api";
import { useProject } from "@/lib/queries/useProjects";
import { useReleasePlan, useReleasePlanMutations } from "@/lib/queries/useReleasePlan";
import { useWorkspace } from "@/lib/workspace";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorText,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  Spinner,
  toneFor,
} from "@/components/ui";

const MILESTONE_CATEGORIES = ["production", "marketing", "distribution", "pr"] as const;
const MILESTONE_STATUS = ["pending", "done"] as const;

// Milestones may arrive nested on the plan under a couple of possible keys.
function milestonesOf(plan: ReleasePlan | null): Milestone[] {
  if (!plan) return [];
  const m = plan.release_milestones ?? [];
  return [...m].sort((a, b) => a.position - b.position);
}

export default function ReleasePlanPage({ params }: { params: { id: string } }) {
  const projectId = params.id;
  const { isReadOnly } = useWorkspace();
  const { data: project } = useProject(projectId);
  const { data: plan, isLoading, error } = useReleasePlan(projectId);
  const { createPlan, updatePlan, addMilestone, updateMilestone, removeMilestone } =
    useReleasePlanMutations(projectId);

  const [milestoneOpen, setMilestoneOpen] = useState(false);

  const milestones = milestonesOf(plan ?? null);
  const doneCount = milestones.filter((m) => m.status === "done").length;
  const pct = milestones.length > 0 ? Math.round((doneCount / milestones.length) * 100) : 0;

  const submitMilestone = (body: MilestoneInput) => {
    if (!plan) return;
    addMilestone.mutate(
      { planId: plan.id, body: { ...body, position: milestones.length } },
      { onSuccess: () => setMilestoneOpen(false) },
    );
  };

  const cycleStatus = (m: Milestone) => {
    const order = MILESTONE_STATUS;
    const next = order[(order.indexOf(m.status as (typeof order)[number]) + 1) % order.length];
    updateMilestone.mutate({ id: m.id, body: { status: next } });
  };

  return (
    <div>
      <div style={{ marginBottom: "0.5rem" }}>
        <Link href="/projects" style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
          ‹ Back to projects
        </Link>
      </div>
      <PageHeader
        title={project ? `${project.title} — Release plan` : "Release plan"}
        subtitle="Coordinate every milestone leading to release day."
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {!isLoading && !plan && (
        <NoPlan
          isReadOnly={isReadOnly}
          pending={createPlan.isPending}
          defaultDate={project?.target_release_date ?? ""}
          onCreate={(release_date) => createPlan.mutate({ release_date })}
        />
      )}

      {plan && (
        <>
          <Card style={{ padding: "1.1rem 1.25rem", marginBottom: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)" }}>Release date</div>
                <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>{plan.release_date}</div>
              </div>
              <Badge tone={toneFor(plan.status)}>{plan.status}</Badge>
              {!isReadOnly && (
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-end" }}>
                  <Input
                    type="date"
                    defaultValue={plan.release_date}
                    onChange={(e) =>
                      e.target.value && updatePlan.mutate({ planId: plan.id, body: { release_date: e.target.value } })
                    }
                    style={{ width: 160 }}
                  />
                  <Button onClick={() => setMilestoneOpen(true)}>+ Milestone</Button>
                </div>
              )}
            </div>
            <div style={{ margin: "0.85rem 0 0.35rem", height: 8, borderRadius: 999, background: "var(--surface-3)", overflow: "hidden" }}>
              <div style={{ width: `${pct}%`, height: "100%", background: "var(--success)", transition: "width 200ms ease" }} />
            </div>
            <div style={{ fontSize: "0.74rem", color: "var(--muted)" }}>
              {doneCount} of {milestones.length} milestones complete ({pct}%)
            </div>
          </Card>

          {milestones.length === 0 && (
            <EmptyState title="No milestones yet" hint="Add milestones to map out the road to release." />
          )}

          {/* Orbital timeline: numbered stage nodes connected by a glowing spine. */}
          <div style={{ position: "relative", paddingLeft: "0.5rem" }}>
            {milestones.map((m, i) => {
              const nodeColor =
                m.status === "done" ? "var(--success)" : m.status === "in_progress" ? "var(--accent)" : "var(--muted-2)";
              const isLast = i === milestones.length - 1;
              return (
                <div key={m.id} style={{ display: "flex", gap: "1rem", position: "relative" }}>
                  {/* Spine + node */}
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 40, flexShrink: 0 }}>
                    <button
                      onClick={() => !isReadOnly && cycleStatus(m)}
                      disabled={isReadOnly}
                      title="Cycle status"
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "50%",
                        border: `2px solid ${nodeColor}`,
                        background: "var(--surface-solid)",
                        color: nodeColor,
                        boxShadow: `0 0 12px ${nodeColor}`,
                        cursor: isReadOnly ? "default" : "pointer",
                        fontFamily: "var(--font-display)",
                        fontWeight: 600,
                        fontSize: "0.9rem",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        zIndex: 1,
                      }}
                    >
                      {m.status === "done" ? "✓" : i + 1}
                    </button>
                    {!isLast && <div style={{ width: 2, flex: 1, minHeight: 24, background: "linear-gradient(var(--border-strong), var(--border))" }} />}
                  </div>

                  {/* Card */}
                  <Card
                    style={{
                      flex: 1,
                      marginBottom: "0.75rem",
                      padding: "0.85rem 1rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.85rem",
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          textDecoration: m.status === "done" ? "line-through" : "none",
                          color: m.status === "done" ? "var(--muted)" : "var(--fg)",
                        }}
                      >
                        {m.title}
                      </div>
                      {m.due_date && <div style={{ fontSize: "0.76rem", color: "var(--muted)" }}>Due {m.due_date}</div>}
                    </div>
                    <Badge>{m.category}</Badge>
                    <Badge tone={toneFor(m.status)}>{m.status.replace("_", " ")}</Badge>
                    {!isReadOnly && (
                      <Button size="sm" variant="danger" onClick={() => removeMilestone.mutate(m.id)}>
                        Delete
                      </Button>
                    )}
                  </Card>
                </div>
              );
            })}
          </div>

          <Modal open={milestoneOpen} onClose={() => setMilestoneOpen(false)} title="Add milestone">
            <MilestoneForm
              key={milestoneOpen ? "open" : "closed"}
              onCancel={() => setMilestoneOpen(false)}
              onSubmit={submitMilestone}
              pending={addMilestone.isPending}
            />
          </Modal>
        </>
      )}
    </div>
  );
}

function NoPlan({
  isReadOnly,
  pending,
  defaultDate,
  onCreate,
}: {
  isReadOnly: boolean;
  pending: boolean;
  defaultDate: string;
  onCreate: (releaseDate: string) => void;
}) {
  const [date, setDate] = useState(defaultDate);
  return (
    <Card style={{ padding: "2rem 1.5rem", textAlign: "center" }}>
      <p style={{ margin: 0, fontWeight: 600 }}>No release plan yet</p>
      <p style={{ margin: "0.4rem 0 1rem", color: "var(--muted)" }}>
        Set a release date to start mapping milestones.
      </p>
      {!isReadOnly && (
        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center", alignItems: "flex-end" }}>
          <div style={{ textAlign: "left" }}>
            <Field label="Release date">
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={{ width: 170 }} />
            </Field>
          </div>
          <Button onClick={() => date && onCreate(date)} disabled={pending || !date}>
            {pending ? "Creating…" : "Create plan"}
          </Button>
        </div>
      )}
    </Card>
  );
}

function MilestoneForm({
  onSubmit,
  onCancel,
  pending,
}: {
  onSubmit: (body: MilestoneInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<(typeof MILESTONE_CATEGORIES)[number]>("production");
  const [status, setStatus] = useState<(typeof MILESTONE_STATUS)[number]>("pending");
  const [dueDate, setDueDate] = useState("");

  const submit = () => {
    if (!title.trim()) return;
    onSubmit({ title: title.trim(), category, status, due_date: dueDate || null });
  };

  return (
    <>
      <Field label="Title">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Master delivered" autoFocus />
      </Field>
      <div className="form-row">
        <Field label="Category">
          <Select value={category} onChange={(e) => setCategory(e.target.value as typeof category)}>
            {MILESTONE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            {MILESTONE_STATUS.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Due date">
        <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </Field>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending || !title.trim()}>
          {pending ? "Adding…" : "Add milestone"}
        </Button>
      </div>
    </>
  );
}
