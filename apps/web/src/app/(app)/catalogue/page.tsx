"use client";

import { useState } from "react";

import { catalogueApi, type CatalogueInput, type CatalogueItem } from "@/lib/api";
import { useCatalogue, useCatalogueMutations } from "@/lib/queries/useCatalogue";
import { useWorkspace, useWorkspaceId } from "@/lib/workspace";
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

const KINDS = ["track", "beat", "stem", "artwork", "document", "video"] as const;
const STATUSES = ["wip", "final", "released"] as const;

function fileSize(bytes: number | null) {
  if (!bytes) return null;
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

// Deterministic cover gradient from the item id, so each tile looks distinct
// and stable across renders (stand-in until real artwork is stored).
function coverGradient(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 360;
  const h2 = (h + 60) % 360;
  return `linear-gradient(135deg, hsl(${h} 55% 22%), hsl(${h2} 60% 32%))`;
}

function kindIcon(kind: string): string {
  switch (kind) {
    case "track":
      return "💿";
    case "beat":
      return "🥁";
    case "stem":
      return "🎚️";
    case "artwork":
      return "🎨";
    case "document":
      return "📄";
    case "video":
      return "🎬";
    default:
      return "📁";
  }
}

export default function CataloguePage() {
  const { isReadOnly } = useWorkspace();
  const ws = useWorkspaceId();
  const { data, isLoading, error } = useCatalogue();
  const { create, remove } = useCatalogueMutations();

  const [open, setOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Create the row, then PUT the file to the returned signed upload URL.
  const submit = async (body: CatalogueInput, file: File | null) => {
    setUploadError(null);
    setBusy(true);
    try {
      const created = await create.mutateAsync({
        ...body,
        file_size: file ? file.size : null,
      });
      if (file && created.upload_url) {
        const res = await fetch(created.upload_url, {
          method: "PUT",
          headers: { "Content-Type": file.type || "application/octet-stream" },
          body: file,
        });
        if (!res.ok) throw new Error(`Upload failed (${res.status})`);
      }
      setOpen(false);
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // Fetch a fresh signed download URL, then open it.
  const download = async (item: CatalogueItem) => {
    if (!ws) return;
    try {
      const res = await catalogueApi.get(ws, item.id);
      if (res.download_url) window.open(res.download_url, "_blank", "noopener");
    } catch (e) {
      setUploadError((e as Error).message);
    }
  };

  return (
    <div>
      <PageHeader
        title="Catalogue"
        subtitle="Masters, stems, and assets in one place."
        action={!isReadOnly && <Button onClick={() => setOpen(true)}>+ Add file</Button>}
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />
      {uploadError && <p style={{ color: "var(--danger)" }}>{uploadError}</p>}

      {data && data.length === 0 && (
        <EmptyState title="No files yet" hint="Upload a master or stem to build your catalogue." />
      )}

      {data && data.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
            gap: "1rem",
          }}
        >
          {data.map((item) => (
            <Card key={item.id} style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              {/* Cover art placeholder — deterministic gradient per item id. */}
              <div
                style={{
                  aspectRatio: "1 / 1",
                  background: coverGradient(item.id),
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span style={{ fontSize: "2rem", opacity: 0.85 }}>{kindIcon(item.kind)}</span>
                <div style={{ position: "absolute", top: 8, left: 8 }}>
                  <Badge tone={toneFor(item.status)}>{item.status}</Badge>
                </div>
              </div>
              <div style={{ padding: "0.85rem", display: "flex", flexDirection: "column", gap: "0.4rem", flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "0.9rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.title}
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--muted)", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <span style={{ textTransform: "capitalize" }}>{item.kind}</span>
                  {item.bpm && <span>· {item.bpm} BPM</span>}
                  {item.key && <span>· {item.key}</span>}
                  {fileSize(item.file_size) && <span>· {fileSize(item.file_size)}</span>}
                </div>
                {item.tags?.length > 0 && (
                  <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
                    {item.tags.slice(0, 3).map((t) => (
                      <Badge key={t} tone="accent">
                        {t}
                      </Badge>
                    ))}
                  </div>
                )}
                <div style={{ display: "flex", gap: "0.35rem", marginTop: "auto", paddingTop: "0.5rem" }}>
                  <Button size="sm" variant="ghost" onClick={() => download(item)} style={{ flex: 1 }}>
                    Download
                  </Button>
                  {!isReadOnly && (
                    <Button size="sm" variant="danger" onClick={() => remove.mutate(item.id)}>
                      ✕
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Add file">
        <CatalogueForm key={open ? "open" : "closed"} onCancel={() => setOpen(false)} onSubmit={submit} pending={busy} />
      </Modal>
    </div>
  );
}

function CatalogueForm({
  onSubmit,
  onCancel,
  pending,
}: {
  onSubmit: (body: CatalogueInput, file: File | null) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<(typeof KINDS)[number]>("track");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("wip");
  const [isrc, setIsrc] = useState("");
  const [bpm, setBpm] = useState("");
  const [key, setKey] = useState("");
  const [tags, setTags] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const submit = () => {
    if (!title.trim()) return;
    onSubmit(
      {
        title: title.trim(),
        kind,
        status,
        isrc: isrc || null,
        bpm: bpm ? parseInt(bpm, 10) : null,
        key: key || null,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      },
      file,
    );
  };

  return (
    <>
      <Field label="Title">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Track master v3" autoFocus />
      </Field>
      <div className="form-row">
        <Field label="Kind">
          <Select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
            {KINDS.map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        </Field>
      </div>
      <div className="form-row">
        <Field label="ISRC">
          <Input value={isrc} onChange={(e) => setIsrc(e.target.value)} placeholder="US-XXX-YY-NNNNN" />
        </Field>
        <Field label="BPM">
          <Input type="number" min="0" value={bpm} onChange={(e) => setBpm(e.target.value)} />
        </Field>
        <Field label="Key">
          <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Am" />
        </Field>
      </div>
      <Field label="Tags (comma separated)">
        <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="lofi, chill" />
      </Field>
      <Field label="File">
        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{ fontSize: "0.82rem", color: "var(--muted)" }}
        />
      </Field>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending || !title.trim()}>
          {pending ? "Uploading…" : "Save"}
        </Button>
      </div>
    </>
  );
}
