"use client";

import Link from "next/link";
import { useState } from "react";

import type { Project, ProjectInput, ProjectStatus } from "@/lib/api";
import { useProjects, useProjectMutations } from "@/lib/queries/useProjects";
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

const STATUSES: ProjectStatus[] = ["idea", "in_progress", "ready", "released", "archived"];
const TYPES = ["single", "ep", "album", "video", "beat_pack", "other"] as const;

export default function ProjectsPage() {
  const { isReadOnly } = useWorkspace();
  const { data, isLoading, error } = useProjects();
  const { create, update, remove } = useProjectMutations();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);

  const openCreate = () => {
    setEditing(null);
    setOpen(true);
  };
  const openEdit = (p: Project) => {
    setEditing(p);
    setOpen(true);
  };

  const submit = (body: ProjectInput) => {
    const onSuccess = () => setOpen(false);
    if (editing) update.mutate({ id: editing.id, body }, { onSuccess });
    else create.mutate(body, { onSuccess });
  };

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="Singles, EPs, and albums in the works."
        action={!isReadOnly && <Button onClick={openCreate}>+ New project</Button>}
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {data && data.length === 0 && (
        <EmptyState title="No projects yet" hint="Start a project to plan your next release." />
      )}

      {data && data.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
            gap: "0.85rem",
          }}
        >
          {data.map((p) => (
            <Card key={p.id} style={{ padding: "1.1rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.5rem" }}>
                <div style={{ fontWeight: 600, fontSize: "1rem", minWidth: 0 }}>{p.title}</div>
                <Badge tone={toneFor(p.status)}>{p.status.replace("_", " ")}</Badge>
              </div>
              <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                <Badge>{p.type}</Badge>
                {p.target_release_date && <Badge tone="accent">{p.target_release_date}</Badge>}
              </div>
              {p.description && (
                <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.5 }}>
                  {p.description}
                </p>
              )}
              <div style={{ display: "flex", gap: "0.35rem", marginTop: "auto", paddingTop: "0.4rem" }}>
                <Link href={`/projects/${p.id}/release-plan`} style={{ flex: 1 }}>
                  <Button size="sm" variant="ghost" style={{ width: "100%" }}>
                    Release plan
                  </Button>
                </Link>
                {!isReadOnly && (
                  <>
                    <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => remove.mutate(p.id)}>
                      Delete
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Edit project" : "New project"}>
        <ProjectForm
          key={editing?.id ?? "new"}
          initial={editing}
          onCancel={() => setOpen(false)}
          onSubmit={submit}
          pending={create.isPending || update.isPending}
        />
      </Modal>
    </div>
  );
}

function ProjectForm({
  initial,
  onSubmit,
  onCancel,
  pending,
}: {
  initial: Project | null;
  onSubmit: (body: ProjectInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [type, setType] = useState(initial?.type ?? "single");
  const [status, setStatus] = useState<ProjectStatus>(initial?.status ?? "idea");
  const [releaseDate, setReleaseDate] = useState(initial?.target_release_date ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");

  const submit = () => {
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      type,
      status,
      target_release_date: releaseDate || null,
      description: description || null,
    });
  };

  return (
    <>
      <Field label="Title">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Untitled release" autoFocus />
      </Field>
      <div style={{ display: "flex", gap: "0.75rem" }}>
        <Field label="Type">
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Target release date">
        <Input type="date" value={releaseDate ?? ""} onChange={(e) => setReleaseDate(e.target.value)} />
      </Field>
      <Field label="Description">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
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
