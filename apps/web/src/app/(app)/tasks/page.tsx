"use client";

import { useState } from "react";

import type { Task, TaskInput, TaskStatus } from "@/lib/api";
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
  const { isReadOnly } = useWorkspace();
  const { data, isLoading, error } = useTasks();
  const { create, update, remove } = useTaskMutations();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);

  const openCreate = () => {
    setEditing(null);
    setOpen(true);
  };
  const openEdit = (t: Task) => {
    setEditing(t);
    setOpen(true);
  };

  const submit = (body: TaskInput) => {
    const onSuccess = () => setOpen(false);
    if (editing) update.mutate({ id: editing.id, body }, { onSuccess });
    else create.mutate(body, { onSuccess });
  };

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
        onClose={() => setOpen(false)}
        editing={editing}
        onSubmit={submit}
        pending={create.isPending || update.isPending}
      />
    </div>
  );
}

function TaskModal({
  open,
  onClose,
  editing,
  onSubmit,
  pending,
}: {
  open: boolean;
  onClose: () => void;
  editing: Task | null;
  onSubmit: (body: TaskInput) => void;
  pending: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} title={editing ? "Edit task" : "New task"}>
      <FormBody
        key={editing?.id ?? "new"}
        initial={editing}
        onCancel={onClose}
        pending={pending}
        onSubmit={onSubmit}
      />
    </Modal>
  );
}

function FormBody({
  initial,
  onSubmit,
  onCancel,
  pending,
}: {
  initial: Task | null;
  onSubmit: (body: TaskInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [status, setStatus] = useState<TaskStatus>(initial?.status ?? "todo");
  const [priority, setPriority] = useState(initial?.priority ?? "medium");
  const [dueDate, setDueDate] = useState(initial?.due_date ?? "");

  const submit = () => {
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      description: description || null,
      status,
      priority,
      due_date: dueDate || null,
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
      <div style={{ display: "flex", gap: "0.75rem" }}>
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as TaskStatus)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Priority">
          <Select value={priority} onChange={(e) => setPriority(e.target.value as typeof priority)}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Due date">
        <Input type="date" value={dueDate ?? ""} onChange={(e) => setDueDate(e.target.value)} />
      </Field>
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
