"use client";

import { useEffect, useState } from "react";

import { CommentsPanel } from "@/components/CommentsPanel";
import type { Task, TaskInput, TaskStatus, WorkspaceMember } from "@/lib/api";
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

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [commenting, setCommenting] = useState<Task | null>(null);
  const members = useTeamMembers(workspaceId);

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

  const toggleDone = (t: Task) =>
    update.mutate({
      id: t.id,
      body: {
        status: t.status === "done" ? "todo" : "done",
        completed_at: t.status === "done" ? null : new Date().toISOString(),
      },
    });

  return (
    <div>
      <PageHeader
        title="Tasks"
        subtitle="Everything on your plate, across projects."
        action={!isReadOnly && <Button onClick={openCreate}>+ New task</Button>}
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {data && data.length === 0 && (
        <EmptyState title="No tasks yet" hint="Create your first task to get moving." />
      )}

      {data && data.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          {data.map((t) => (
            <Card
              key={t.id}
              className="task-list-row"
              style={{ padding: "0.85rem 1rem", display: "flex", alignItems: "center", gap: "0.85rem" }}
            >
              <input
                type="checkbox"
                checked={t.status === "done"}
                onChange={() => !isReadOnly && toggleDone(t)}
                disabled={isReadOnly}
                style={{ width: 18, height: 18, accentColor: "var(--accent)", cursor: "pointer" }}
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
              {plan === "team" && <Badge>{t.approval_status.replace("_", " ")}</Badge>}
              {plan === "team" && !isReadOnly && t.approval_status !== "pending" && (
                <Button size="sm" variant="ghost" onClick={() => submitApproval.mutate(t.id)}>
                  Submit
                </Button>
              )}
              {plan === "team" && t.approval_status === "pending" && (role === "owner" || role === "admin") && (
                <div style={{ display: "flex", gap: "0.35rem" }}>
                  <Button size="sm" onClick={() => approve.mutate({ id: t.id })}>Approve</Button>
                  <Button size="sm" variant="danger" onClick={() => reject.mutate({ id: t.id })}>Reject</Button>
                </div>
              )}
              <Button size="sm" variant="ghost" onClick={() => setCommenting(t)}>
                Comments
              </Button>
              {!isReadOnly && (
                <div style={{ display: "flex", gap: "0.35rem" }}>
                  <Button size="sm" variant="ghost" onClick={() => openEdit(t)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => remove.mutate(t.id)}>
                    Delete
                  </Button>
                </div>
              )}
            </Card>
          ))}
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
    </div>
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
