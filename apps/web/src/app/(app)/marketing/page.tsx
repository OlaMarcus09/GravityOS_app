"use client";

import { useState } from "react";

import type { Campaign, CampaignInput, ContentInput, ContentPiece } from "@/lib/api";
import { useCampaigns, useMarketingMutations } from "@/lib/queries/useMarketing";
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
  Textarea,
  Spinner,
  toneFor,
} from "@/components/ui";

const CAMPAIGN_OBJECTIVES = ["awareness", "engagement", "conversion", "release_hype"] as const;
const CAMPAIGN_STATUS = ["planned", "active", "completed"] as const;
const CONTENT_STATUS = ["idea", "drafted", "scheduled", "published"] as const;
const PLATFORMS = ["instagram", "tiktok", "x", "youtube", "other"] as const;
const FORMATS = ["post", "reel", "story", "video", "other"] as const;

// Content pieces may arrive on a nested field; normalize.
type CampaignWithContent = Campaign & { content?: ContentPiece[]; content_pieces?: ContentPiece[] };

function contentOf(c: CampaignWithContent): ContentPiece[] {
  return c.content ?? c.content_pieces ?? [];
}

export default function MarketingPage() {
  const { isReadOnly } = useWorkspace();
  const { data, isLoading, error } = useCampaigns();
  const { create, update, addContent, removeContent } = useMarketingMutations();

  const [campaignOpen, setCampaignOpen] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null);
  const [contentFor, setContentFor] = useState<string | null>(null);

  const openCreate = () => {
    setEditingCampaign(null);
    setCampaignOpen(true);
  };

  const submitCampaign = (body: CampaignInput) => {
    const onSuccess = () => setCampaignOpen(false);
    if (editingCampaign) update.mutate({ id: editingCampaign.id, body }, { onSuccess });
    else create.mutate(body, { onSuccess });
  };

  const submitContent = (body: ContentInput) => {
    if (!contentFor) return;
    addContent.mutate({ campaignId: contentFor, body }, { onSuccess: () => setContentFor(null) });
  };

  const campaigns = (data ?? []) as CampaignWithContent[];

  return (
    <div>
      <PageHeader
        title="Marketing"
        subtitle="Plan campaigns and the content behind them."
        action={!isReadOnly && <Button onClick={openCreate}>+ New campaign</Button>}
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {data && data.length === 0 && (
        <EmptyState title="No campaigns yet" hint="Plan a campaign to organize your rollout." />
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {campaigns.map((c) => {
          const pieces = contentOf(c);
          return (
            <Card key={c.id} style={{ padding: "1.1rem 1.25rem" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.75rem" }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontWeight: 600, fontSize: "1.05rem" }}>{c.name}</span>
                    <Badge tone={toneFor(c.status)}>{c.status}</Badge>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginTop: "0.15rem" }}>
                    {c.objective} · {c.start_date} → {c.end_date}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.35rem" }}>
                  {!isReadOnly && (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => setContentFor(c.id)}>
                        + Content
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setEditingCampaign(c); setCampaignOpen(true); }}>
                        Edit
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {pieces.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", marginTop: "0.85rem" }}>
                  {pieces.map((p) => (
                    <div
                      key={p.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.6rem",
                        padding: "0.45rem 0.6rem",
                        background: "var(--surface-2)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      <Badge tone="accent">{p.platform}</Badge>
                      <Badge>{p.format}</Badge>
                      <span style={{ flex: 1, minWidth: 0, fontSize: "0.84rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {p.caption || <span style={{ color: "var(--muted)" }}>No caption</span>}
                      </span>
                      {p.scheduled_at && (
                        <span style={{ fontSize: "0.74rem", color: "var(--muted)" }}>
                          {new Date(p.scheduled_at).toLocaleDateString()}
                        </span>
                      )}
                      <Badge tone={toneFor(p.status)}>{p.status}</Badge>
                      {!isReadOnly && (
                        <button
                          onClick={() => removeContent.mutate(p.id)}
                          aria-label="Remove content"
                          style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: "1rem" }}
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Modal open={campaignOpen} onClose={() => setCampaignOpen(false)} title={editingCampaign ? "Edit campaign" : "New campaign"}>
        <CampaignForm
          key={editingCampaign?.id ?? "new"}
          initial={editingCampaign}
          onCancel={() => setCampaignOpen(false)}
          onSubmit={submitCampaign}
          pending={create.isPending || update.isPending}
        />
      </Modal>

      <Modal open={!!contentFor} onClose={() => setContentFor(null)} title="Add content">
        <ContentForm key={contentFor ?? "none"} onCancel={() => setContentFor(null)} onSubmit={submitContent} pending={addContent.isPending} />
      </Modal>
    </div>
  );
}

function CampaignForm({
  initial,
  onSubmit,
  onCancel,
  pending,
}: {
  initial: Campaign | null;
  onSubmit: (body: CampaignInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [objective, setObjective] = useState(initial?.objective ?? "awareness");
  const [status, setStatus] = useState(initial?.status ?? "planned");
  const [startDate, setStartDate] = useState(initial?.start_date ?? "");
  const [endDate, setEndDate] = useState(initial?.end_date ?? "");

  const submit = () => {
    if (!name.trim() || !objective || !startDate || !endDate) return;
    onSubmit({
      name: name.trim(),
      objective,
      status,
      start_date: startDate,
      end_date: endDate,
    });
  };

  return (
    <>
      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Single launch" autoFocus />
      </Field>
      <Field label="Objective">
        <Select value={objective} onChange={(e) => setObjective(e.target.value)}>
          {CAMPAIGN_OBJECTIVES.map((o) => (
            <option key={o} value={o}>
              {o.replace("_", " ")}
            </option>
          ))}
        </Select>
      </Field>
      <div className="form-row">
        <Field label="Start">
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </Field>
        <Field label="End">
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </Field>
      </div>
      <Field label="Status">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {CAMPAIGN_STATUS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </Field>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending || !name.trim() || !objective || !startDate || !endDate}>
          {pending ? "Saving…" : "Save"}
        </Button>
      </div>
    </>
  );
}

function ContentForm({
  onSubmit,
  onCancel,
  pending,
}: {
  onSubmit: (body: ContentInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>("instagram");
  const [format, setFormat] = useState<(typeof FORMATS)[number]>("reel");
  const [status, setStatus] = useState<(typeof CONTENT_STATUS)[number]>("idea");
  const [scheduledAt, setScheduledAt] = useState("");
  const [caption, setCaption] = useState("");

  const submit = () => {
    onSubmit({
      platform,
      format,
      status,
      scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      caption: caption || null,
    });
  };

  return (
    <>
      <div className="form-row">
        <Field label="Platform">
          <Select value={platform} onChange={(e) => setPlatform(e.target.value as typeof platform)}>
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
        </Field>
        <Field label="Format">
          <Select value={format} onChange={(e) => setFormat(e.target.value as typeof format)}>
            {FORMATS.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </Select>
        </Field>
      </div>
      <div className="form-row">
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            {CONTENT_STATUS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        </Field>
        <Field label="Scheduled">
          <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
        </Field>
      </div>
      <Field label="Caption">
        <Textarea value={caption} onChange={(e) => setCaption(e.target.value)} rows={3} />
      </Field>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending}>
          {pending ? "Adding…" : "Add content"}
        </Button>
      </div>
    </>
  );
}
