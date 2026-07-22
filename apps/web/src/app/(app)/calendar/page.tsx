"use client";

import { useMemo, useState } from "react";

import type { CalendarEvent, EventInput } from "@/lib/api";
import { useCalendar, useCalendarMutations } from "@/lib/queries/useCalendar";
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

const EVENT_TYPES = ["content", "meeting", "deadline", "release", "personal"] as const;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// --- date helpers ----------------------------------------------------------

function iso(d: Date) {
  return d.toISOString().slice(0, 10);
}
function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
function endOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}
function addMonths(d: Date, n: number) {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}
// Build the 6x7 grid of days covering the visible month (leading/trailing days
// from adjacent months fill the edges).
function buildGrid(month: Date): Date[] {
  const first = startOfMonth(month);
  const start = new Date(first);
  start.setDate(first.getDate() - first.getDay());
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

export default function CalendarPage() {
  const { isReadOnly } = useWorkspace();
  const [month, setMonth] = useState(() => startOfMonth(new Date()));

  const from = iso(startOfMonth(month));
  const to = iso(endOfMonth(month));
  const { data, isLoading, error } = useCalendar(from, to);
  const { create, update, remove } = useCalendarMutations();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [seedDate, setSeedDate] = useState<string | null>(null);

  const grid = useMemo(() => buildGrid(month), [month]);
  const todayIso = iso(new Date());

  // Bucket events and task-due-dates by day for quick per-cell lookup.
  const byDay = useMemo(() => {
    const map = new Map<string, { events: CalendarEvent[]; dues: string[] }>();
    const bump = (key: string) => {
      if (!map.has(key)) map.set(key, { events: [], dues: [] });
      return map.get(key)!;
    };
    data?.events.forEach((e) => bump(e.starts_at.slice(0, 10)).events.push(e));
    data?.task_due_dates.forEach((t) => bump(t.due_date).dues.push(t.title));
    return map;
  }, [data]);

  const openCreate = (day?: string) => {
    setEditing(null);
    setSeedDate(day ?? null);
    setOpen(true);
  };
  const openEdit = (e: CalendarEvent) => {
    setEditing(e);
    setSeedDate(null);
    setOpen(true);
  };

  const submit = (body: EventInput) => {
    const onSuccess = () => setOpen(false);
    if (editing) update.mutate({ id: editing.id, body }, { onSuccess });
    else create.mutate(body, { onSuccess });
  };

  const monthLabel = month.toLocaleString(undefined, { month: "long", year: "numeric" });

  return (
    <div>
      <PageHeader
        title="Calendar"
        subtitle="Sessions, releases, and deadlines at a glance."
        action={!isReadOnly && <Button onClick={() => openCreate()}>+ New event</Button>}
      />

      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <Button size="sm" variant="ghost" onClick={() => setMonth(addMonths(month, -1))}>
          ‹ Prev
        </Button>
        <strong style={{ minWidth: 160, textAlign: "center" }}>{monthLabel}</strong>
        <Button size="sm" variant="ghost" onClick={() => setMonth(addMonths(month, 1))}>
          Next ›
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMonth(startOfMonth(new Date()))}>
          Today
        </Button>
      </div>

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {!isLoading && !error && data && data.events.length === 0 && (
        <EmptyState
          title="Nothing scheduled yet"
          hint="Add your first session, release, or deadline to fill the calendar."
          action={!isReadOnly && <Button onClick={() => openCreate()}>+ New event</Button>}
        />
      )}

      <Card style={{ padding: "0.5rem", overflow: "hidden" }}>
        <div className="cal-grid">
          {WEEKDAYS.map((w) => (
            <div
              key={w}
              style={{ textAlign: "center", fontSize: "0.72rem", color: "var(--muted)", fontWeight: 600, padding: "0.3rem 0" }}
            >
              {w}
            </div>
          ))}
          {grid.map((d) => {
            const key = iso(d);
            const cell = byDay.get(key);
            const inMonth = d.getMonth() === month.getMonth();
            const isToday = key === todayIso;
            return (
              <div
                key={key}
                className="cal-cell"
                onClick={() => !isReadOnly && openCreate(key)}
                style={{
                  borderRadius: "var(--radius-sm)",
                  border: isToday ? "1px solid var(--accent)" : "1px solid var(--border)",
                  background: inMonth ? "var(--surface-2)" : "transparent",
                  opacity: inMonth ? 1 : 0.4,
                  cursor: isReadOnly ? "default" : "pointer",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.2rem",
                }}
              >
                <span style={{ fontSize: "0.72rem", color: isToday ? "var(--accent)" : "var(--muted)", fontWeight: isToday ? 700 : 500 }}>
                  {d.getDate()}
                </span>
                {cell?.events.map((e) => (
                  <button
                    key={e.id}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      openEdit(e);
                    }}
                    title={e.title}
                    style={{
                      textAlign: "left",
                      fontSize: "0.68rem",
                      padding: "0.1rem 0.3rem",
                      borderRadius: 4,
                      border: "none",
                      cursor: "pointer",
                      background: "var(--accent-soft)",
                      color: "var(--accent-hover)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {e.title}
                  </button>
                ))}
                {cell?.dues.map((title, i) => (
                  <span
                    key={`due-${i}`}
                    title={`Task due: ${title}`}
                    style={{
                      fontSize: "0.68rem",
                      padding: "0.1rem 0.3rem",
                      borderRadius: 4,
                      background: "var(--warning-soft)",
                      color: "var(--warning)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    ⚑ {title}
                  </span>
                ))}
              </div>
            );
          })}
        </div>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Edit event" : "New event"}>
        <EventForm
          key={editing?.id ?? seedDate ?? "new"}
          initial={editing}
          seedDate={seedDate}
          onCancel={() => setOpen(false)}
          onSubmit={submit}
          onDelete={editing && !isReadOnly ? () => remove.mutate(editing.id, { onSuccess: () => setOpen(false) }) : undefined}
          pending={create.isPending || update.isPending}
        />
      </Modal>
    </div>
  );
}

// Convert a stored ISO timestamp to the value shape a datetime-local input wants.
function toLocalInput(isoStr: string | null): string {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function EventForm({
  initial,
  seedDate,
  onSubmit,
  onCancel,
  onDelete,
  pending,
}: {
  initial: CalendarEvent | null;
  seedDate: string | null;
  onSubmit: (body: EventInput) => void;
  onCancel: () => void;
  onDelete?: () => void;
  pending: boolean;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [type, setType] = useState(initial?.type ?? "content");
  const [allDay, setAllDay] = useState(initial?.all_day ?? false);
  const [startsAt, setStartsAt] = useState(
    initial ? toLocalInput(initial.starts_at) : seedDate ? `${seedDate}T12:00` : "",
  );
  const [endsAt, setEndsAt] = useState(initial ? toLocalInput(initial.ends_at) : "");
  const [notes, setNotes] = useState(initial?.notes ?? "");

  const submit = () => {
    if (!title.trim() || !startsAt) return;
    onSubmit({
      title: title.trim(),
      type,
      all_day: allDay,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: endsAt ? new Date(endsAt).toISOString() : null,
      notes: notes || null,
    });
  };

  return (
    <>
      <Field label="Title">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Studio session" autoFocus />
      </Field>
      <div className="form-row" style={{ alignItems: "flex-end" }}>
        <Field label="Type">
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: "var(--muted)", paddingBottom: "0.6rem" }}>
          <input
            type="checkbox"
            checked={allDay}
            onChange={(e) => setAllDay(e.target.checked)}
            style={{ width: 16, height: 16, accentColor: "var(--accent)" }}
          />
          All day
        </label>
      </div>
      <div className="form-row">
        <Field label="Starts">
          <Input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
        </Field>
        <Field label="Ends">
          <Input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
        </Field>
      </div>
      <Field label="Notes">
        <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
      </Field>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", marginTop: "0.5rem" }}>
        <span>
          {onDelete && (
            <Button variant="danger" onClick={onDelete}>
              Delete
            </Button>
          )}
        </span>
        <span style={{ display: "flex", gap: "0.5rem" }}>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={pending || !title.trim() || !startsAt}>
            {pending ? "Saving…" : "Save"}
          </Button>
        </span>
      </div>
    </>
  );
}
