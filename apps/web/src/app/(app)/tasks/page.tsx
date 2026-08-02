"use client";

import { useEffect, useState } from "react";

import { CommentsPanel } from "@/components/CommentsPanel";
import type { Task, TaskInput, TaskStatus, WorkspaceMember } from "@/lib/api";
import { useMe } from "@/lib/queries/useMe";
import { useTeamMembers } from "@/lib/queries/useTeam";
import { useTasks, useTaskMutations } from "@/lib/queries/useTasks";
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
  Textarea,
  toneFor,
} from "@/components/ui";

const STATUSES: TaskStatus[] = ["todo", "in_progress", "blocked", "done"];
const PRIORITIES = ["low", "medium", "high"] as const;

export default function TasksPage() {
  const { isReadOnly, workspaceId, role, plan } = useWorkspace();
  const { data, isLoading, error } = useTasks();
  const { create, update, remove, submitApproval, approve, reject } = useTaskMutations();
  const { data: me } = useMe();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [commenting, setCommenting] = useState<Task | null>(null);
  const [reviewing, setReviewing] = useState<{ task: Task; decision: "approve" | "reject" } | null>(null);
  const [actionError, setActionError] = useState<{ taskId: string; error: Error } | null>(null);
  const members = useTeamMembers(workspaceId);
  const canReview = plan === "team" && (role === "owner" || role === "admin");
  const pendingReviews = data?.filter((task) => task.approval_status === "pending") ?? [];
  const memberNames = new Map(
    (members.data ?? []).map((member) => [member.user_id, member.profiles?.display_name || "Team member"]),
  );

  useEffect(() => {
    if (!data) return;
    const targetId = new URLSearchParams(window.location.search).get("comments");
    if (targetId) setCommenting(data.find((task) => task.id === targetId) ?? null);
  }, [data]);

  const openCreate = () => {
    setEditing(null);
    setOpen(true);
  };
  const openEdit = (t: Task) => {
    setEditing(t);
    setOpen(true);
  };

  const submit = (body: TaskInput) => {
    const onSuccess = () => { setOpen(false); setMutationError(null); };
    if (editing) update.mutate({ id: editing.id, body }, { onSuccess, onError: (e) => setMutationError(e) });
    else create.mutate(body, { onSuccess, onError: (e) => setMutationError(e) });
  };
  const [mutationError, setMutationError] = useState<Error | null>(null);

  const toggleDone = (t: Task) => {
    setActionError(null);
    update.mutate({
      id: t.id,
      body: {
        status: t.status === "done" ? "todo" : "done",
        completed_at: t.status === "done" ? null : new Date().toISOString(),
      },
    }, { onError: (e) => setActionError({ taskId: t.id, error: e }) });
  };

  const submitForApproval = (task: Task) => {
    setActionError(null);
    submitApproval.mutate(task.id, {
      onError: (e) => setActionError({ taskId: task.id, error: e }),
    });
  };

  const deleteTask = (task: Task) => {
    setActionError(null);
    remove.mutate(task.id, {
      onError: (e) => setActionError({ taskId: task.id, error: e }),
    });
  };

  const reviewTask = (note: string) => {
    if (!reviewing) return;
    setActionError(null);
    const mutationOptions = {
      onSuccess: () => setReviewing(null),
      onError: (e: Error) => setActionError({ taskId: reviewing.task.id, error: e }),
    };
    if (reviewing.decision === "approve") approve.mutate(
      { id: reviewing.task.id, note: note.trim() || undefined },
      mutationOptions,
    );
    else reject.mutate({ id: reviewing.task.id, note: note.trim() || undefined }, mutationOptions);
  };

  const displayName = (userId: string | null) => {
    if (!userId) return "Unknown team member";
    if (userId === me?.user_id) return "You";
    return memberNames.get(userId) ?? "Team member";
  };

  return (
    <div>
      <PageHeader
        title="Tasks"
        subtitle="Everything on your plate, across projects."
        action={!isReadOnly && <Button onClick={openCreate}>+ New task</Button>}
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {canReview && pendingReviews.length > 0 && (
        <section style={{ marginBottom: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "1rem", marginBottom: "0.6rem" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "1rem" }}>Needs review</h2>
              <p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.8rem" }}>
                {pendingReviews.length} {pendingReviews.length === 1 ? "task is" : "tasks are"} waiting for a decision.
              </p>
            </div>
            <Badge tone="warning">{pendingReviews.length} pending</Badge>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {pendingReviews.map((task) => {
              const isOwnSubmission = task.approval_submitted_by === me?.user_id;
              const reviewPending = (approve.isPending && approve.variables?.id === task.id)
                || (reject.isPending && reject.variables?.id === task.id);
              return (
                <Card key={`review-${task.id}`} style={{ padding: "0.9rem 1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.8rem", flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 220 }}>
                      <div style={{ fontWeight: 600 }}>{task.title}</div>
                      <div style={{ marginTop: "0.2rem", color: "var(--muted)", fontSize: "0.78rem" }}>
                        Submitted by {displayName(task.approval_submitted_by)}
                        {task.due_date ? ` · Due ${task.due_date}` : ""}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <Button
                        size="sm"
                        disabled={isOwnSubmission || reviewPending}
                        onClick={() => setReviewing({ task, decision: "approve" })}
                      >
                        {approve.isPending && approve.variables?.id === task.id ? "Approving…" : "Approve"}
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={isOwnSubmission || reviewPending}
                        onClick={() => setReviewing({ task, decision: "reject" })}
                      >
                        {reject.isPending && reject.variables?.id === task.id ? "Rejecting…" : "Reject"}
                      </Button>
                    </div>
                  </div>
                  {isOwnSubmission && (
                    <p style={{ margin: "0.55rem 0 0", color: "var(--warning)", fontSize: "0.78rem" }}>
                      Another owner or admin must review a task you submitted.
                    </p>
                  )}
                  {actionError?.taskId === task.id && <ErrorText error={actionError.error} />}
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {data && data.length === 0 && (
        <EmptyState title="No tasks yet" hint="Create your first task to get moving." />
      )}

      {data && data.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          {data.map((t) => {
            const submitting = submitApproval.isPending && submitApproval.variables === t.id;
            const deleting = remove.isPending && remove.variables === t.id;
            const updating = update.isPending && update.variables?.id === t.id;
            const approvalLocked = plan === "team" && (t.approval_status === "pending" || t.approval_status === "approved");
            return (
              <Card
                key={t.id}
                className="task-list-row"
                style={{ padding: "0.85rem 1rem", display: "flex", alignItems: "center", gap: "0.85rem" }}
              >
                <input
                  type="checkbox"
                  checked={t.status === "done"}
                  onChange={() => !isReadOnly && toggleDone(t)}
                  disabled={isReadOnly || updating || approvalLocked}
                  style={{ width: 18, height: 18, accentColor: "var(--accent)", cursor: isReadOnly || approvalLocked ? "not-allowed" : "pointer" }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: 550,
                      textDecoration: t.status === "done" ? "line-through" : "none",
                      color: t.status === "done" ? "var(--muted)" : "var(--fg)",
                    }}
                  >
                    {t.title}
                  </div>
                  {t.due_date && (
                    <div style={{ fontSize: "0.78rem", color: "var(--muted)" }}>Due {t.due_date}</div>
                  )}
                </div>
                <Badge tone={toneFor(t.priority)}>{t.priority}</Badge>
                <Badge tone={toneFor(t.status)}>{t.status.replace("_", " ")}</Badge>
                {plan === "team" && <Badge tone={toneFor(t.approval_status)}>{t.approval_status.replace("_", " ")}</Badge>}
                {plan === "team" && !isReadOnly && (t.approval_status === "not_required" || t.approval_status === "rejected") && (
                  <Button size="sm" variant="ghost" disabled={submitting} onClick={() => submitForApproval(t)}>
                    {submitting ? "Submitting…" : t.approval_status === "rejected" ? "Resubmit" : "Submit"}
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setCommenting(t)}>
                  Comments
                </Button>
                {!isReadOnly && (
                  <div style={{ display: "flex", gap: "0.35rem" }}>
                    <Button size="sm" variant="ghost" disabled={updating || approvalLocked} onClick={() => openEdit(t)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="danger" disabled={deleting} onClick={() => deleteTask(t)}>
                      {deleting ? "Deleting…" : "Delete"}
                    </Button>
                  </div>
                )}
                {plan === "team" && t.approval_status !== "pending" && (t.approval_reviewed_at || t.approval_note) && (
                  <div style={{ flexBasis: "100%", paddingLeft: 32, color: "var(--muted)", fontSize: "0.78rem" }}>
                    {t.approval_reviewed_at && (
                      <span>
                        {t.approval_status === "approved" ? "Approved" : "Rejected"} by {displayName(t.approval_reviewed_by)} on {new Date(t.approval_reviewed_at).toLocaleString()}
                      </span>
                    )}
                    {t.approval_note && <div style={{ marginTop: "0.2rem", color: "var(--fg)" }}>“{t.approval_note}”</div>}
                  </div>
                )}
                {actionError?.taskId === t.id && (
                  <div style={{ flexBasis: "100%", paddingLeft: 32 }}><ErrorText error={actionError.error} /></div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <TaskModal
        open={open}
        onClose={() => { setOpen(false); setMutationError(null); }}
        editing={editing}
        onSubmit={submit}
        pending={create.isPending || update.isPending}
        error={mutationError}
        members={members.data ?? []}
      />
      <Modal open={Boolean(commenting)} onClose={() => setCommenting(null)} title={commenting ? `${commenting.title} · Comments` : "Comments"}>
        {commenting && <CommentsPanel targetType="task" targetId={commenting.id} />}
      </Modal>
      <ReviewModal
        review={reviewing}
        onClose={() => { setReviewing(null); setActionError(null); }}
        onSubmit={reviewTask}
        pending={approve.isPending || reject.isPending}
        error={reviewing && actionError?.taskId === reviewing.task.id ? actionError.error : null}
      />
    </div>
  );
}

function ReviewModal({
  review,
  onClose,
  onSubmit,
  pending,
  error,
}: {
  review: { task: Task; decision: "approve" | "reject" } | null;
  onClose: () => void;
  onSubmit: (note: string) => void;
  pending: boolean;
  error: Error | null;
}) {
  const [note, setNote] = useState("");
  useEffect(() => setNote(""), [review?.task.id, review?.decision]);
  if (!review) return null;
  const approving = review.decision === "approve";

  return (
    <Modal
      open
      onClose={pending ? () => undefined : onClose}
      title={`${approving ? "Approve" : "Reject"} · ${review.task.title}`}
    >
      <Field label={approving ? "Approval note (optional)" : "Rejection note (recommended)"}>
        <Textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={1000}
          rows={4}
          autoFocus
          placeholder={approving ? "Add context for the team…" : "Explain what needs to change…"}
        />
      </Field>
      <div style={{ color: "var(--muted)", fontSize: "0.72rem", textAlign: "right" }}>{note.length}/1000</div>
      <ErrorText error={error} />
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
        <Button variant="ghost" disabled={pending} onClick={onClose}>Cancel</Button>
        <Button variant={approving ? "primary" : "danger"} disabled={pending} onClick={() => onSubmit(note)}>
          {pending ? (approving ? "Approving…" : "Rejecting…") : (approving ? "Approve task" : "Reject task")}
        </Button>
      </div>
    </Modal>
  );
}

function TaskModal({
  open,
  onClose,
  editing,
  onSubmit,
  pending,
  error,
  members,
}: {
  open: boolean;
  onClose: () => void;
  editing: Task | null;
  onSubmit: (body: TaskInput) => void;
  pending: boolean;
  error: Error | null;
  members: WorkspaceMember[];
}) {
  return (
    <Modal open={open} onClose={onClose} title={editing ? "Edit task" : "New task"}>
      <FormBody
        key={editing?.id ?? "new"}
        initial={editing}
        onCancel={onClose}
        pending={pending}
        onSubmit={onSubmit}
        error={error}
        members={members}
      />
    </Modal>
  );
}

function FormBody({
  initial,
  onSubmit,
  onCancel,
  pending,
  error,
  members,
}: {
  initial: Task | null;
  onSubmit: (body: TaskInput) => void;
  onCancel: () => void;
  pending: boolean;
  error: Error | null;
  members: WorkspaceMember[];
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [status, setStatus] = useState<TaskStatus>(initial?.status ?? "todo");
  const [priority, setPriority] = useState(initial?.priority ?? "medium");
  const [dueDate, setDueDate] = useState(initial?.due_date ?? "");
  const [assigneeId, setAssigneeId] = useState(initial?.assignee_id ?? "");

  const submit = () => {
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      description: description || null,
      status,
      priority,
      due_date: dueDate || null,
      assignee_id: assigneeId || null,
    });
  };

  return (
    <>
      <Field label="Title">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Finish the master" autoFocus />
      </Field>
      <Field label="Description">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </Field>
      <div className="form-row">
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as TaskStatus)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace("_", " ")}</option>
            ))}
          </Select>
        </Field>
        <Field label="Priority">
          <Select value={priority} onChange={(e) => setPriority(e.target.value as typeof priority)}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Due date">
        <Input type="date" value={dueDate ?? ""} onChange={(e) => setDueDate(e.target.value)} />
      </Field>
      <Field label="Assignee">
        <Select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
          <option value="">Unassigned</option>
          {members.map((member) => (
            <option key={member.user_id} value={member.user_id}>
              {member.profiles?.display_name || "Team member"}
            </option>
          ))}
        </Select>
      </Field>
      <ErrorText error={error} />
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending || !title.trim()}>
          {pending ? "Saving…" : "Save"}
        </Button>
      </div>
    </>
  );
}
