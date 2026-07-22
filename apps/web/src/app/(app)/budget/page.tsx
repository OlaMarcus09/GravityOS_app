"use client";

import { useState } from "react";

import type { Budget, BudgetInput, BudgetItem, BudgetItemInput } from "@/lib/api";
import { useBudgets, useBudgetMutations } from "@/lib/queries/useBudgets";
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
  Spinner,
} from "@/components/ui";

const CATEGORIES = ["production", "marketing", "visuals", "distribution", "other"] as const;

function money(amount: string | number | null, currency = "USD") {
  const n = typeof amount === "string" ? parseFloat(amount) : amount ?? 0;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currency}`;
  }
}

// Sum a budget's item planned/actual amounts for the progress summary.
function totals(items: BudgetItem[]) {
  return items.reduce(
    (acc, it) => {
      acc.planned += parseFloat(it.planned_amount) || 0;
      acc.actual += parseFloat(it.actual_amount ?? "0") || 0;
      return acc;
    },
    { planned: 0, actual: 0 },
  );
}

// The API returns budgets but items may arrive on a nested field; normalize.
type BudgetWithItems = Budget & { budget_items?: BudgetItem[]; items?: BudgetItem[] };

function itemsOf(b: BudgetWithItems): BudgetItem[] {
  return b.budget_items ?? b.items ?? [];
}

export default function BudgetPage() {
  const { isReadOnly } = useWorkspace();
  const { data, isLoading, error } = useBudgets();
  const { create, update, addItem, updateItem, removeItem } = useBudgetMutations();

  const [budgetOpen, setBudgetOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState<Budget | null>(null);
  const [itemFor, setItemFor] = useState<string | null>(null);

  const openCreateBudget = () => {
    setEditingBudget(null);
    setBudgetOpen(true);
  };

  const submitBudget = (body: BudgetInput) => {
    const onSuccess = () => setBudgetOpen(false);
    if (editingBudget) update.mutate({ id: editingBudget.id, body }, { onSuccess });
    else create.mutate(body, { onSuccess });
  };

  const submitItem = (body: BudgetItemInput) => {
    if (!itemFor) return;
    addItem.mutate({ budgetId: itemFor, body }, { onSuccess: () => setItemFor(null) });
  };

  const budgets = (data ?? []) as BudgetWithItems[];

  return (
    <div>
      <PageHeader
        title="Budget"
        subtitle="Track spend against plan across your projects."
        action={!isReadOnly && <Button onClick={openCreateBudget}>+ New budget</Button>}
      />

      {isLoading && <Spinner />}
      <ErrorText error={error} />

      {data && data.length === 0 && (
        <EmptyState title="No budgets yet" hint="Create a budget to start tracking spend." />
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {budgets.map((b) => {
          const items = itemsOf(b);
          const t = totals(items);
          const pct = t.planned > 0 ? Math.min(100, Math.round((t.actual / t.planned) * 100)) : 0;
          const over = t.actual > t.planned && t.planned > 0;
          return (
            <Card key={b.id} style={{ padding: "1.1rem 1.25rem" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.75rem" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>{b.name}</div>
                  <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginTop: "0.15rem" }}>
                    {money(t.actual, b.currency)} spent of {money(b.total_amount, b.currency)} budget
                  </div>
                </div>
                {!isReadOnly && (
                  <Button size="sm" variant="ghost" onClick={() => setItemFor(b.id)}>
                    + Line item
                  </Button>
                )}
              </div>

              <div style={{ margin: "0.85rem 0 0.4rem", height: 8, borderRadius: 999, background: "var(--surface-3)", overflow: "hidden" }}>
                <div
                  style={{
                    width: `${pct}%`,
                    height: "100%",
                    background: over ? "var(--danger)" : "var(--accent)",
                    transition: "width 200ms ease",
                  }}
                />
              </div>
              <div style={{ fontSize: "0.74rem", color: over ? "var(--danger)" : "var(--muted)", marginBottom: "0.6rem" }}>
                {pct}% of planned{over ? " — over budget" : ""}
              </div>

              {items.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                  {items.map((it) => (
                    <div
                      key={it.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.6rem",
                        padding: "0.45rem 0.6rem",
                        background: "var(--surface-2)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      <Badge>{it.category}</Badge>
                      <span style={{ flex: 1, minWidth: 0, fontSize: "0.85rem" }}>{it.label}</span>
                      <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                        {money(it.actual_amount, b.currency)} / {money(it.planned_amount, b.currency)}
                      </span>
                      {!isReadOnly && (
                        <button
                          onClick={() => removeItem.mutate(it.id)}
                          aria-label="Remove item"
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

      <Modal open={budgetOpen} onClose={() => setBudgetOpen(false)} title={editingBudget ? "Edit budget" : "New budget"}>
        <BudgetForm
          key={editingBudget?.id ?? "new"}
          initial={editingBudget}
          onCancel={() => setBudgetOpen(false)}
          onSubmit={submitBudget}
          pending={create.isPending || update.isPending}
        />
      </Modal>

      <Modal open={!!itemFor} onClose={() => setItemFor(null)} title="Add line item">
        <ItemForm key={itemFor ?? "none"} onCancel={() => setItemFor(null)} onSubmit={submitItem} pending={addItem.isPending} />
      </Modal>
    </div>
  );
}

function BudgetForm({
  initial,
  onSubmit,
  onCancel,
  pending,
}: {
  initial: Budget | null;
  onSubmit: (body: BudgetInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [total, setTotal] = useState(initial?.total_amount ?? "");
  const [currency, setCurrency] = useState(initial?.currency ?? "USD");

  const submit = () => {
    const amount = parseFloat(total);
    if (!name.trim() || Number.isNaN(amount)) return;
    onSubmit({ name: name.trim(), total_amount: amount, currency });
  };

  return (
    <>
      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Album rollout" autoFocus />
      </Field>
      <div className="form-row">
        <Field label="Total amount">
          <Input type="number" min="0" step="0.01" value={total} onChange={(e) => setTotal(e.target.value)} placeholder="5000" />
        </Field>
        <Field label="Currency">
          <Input value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} maxLength={3} />
        </Field>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending || !name.trim() || !total}>
          {pending ? "Saving…" : "Save"}
        </Button>
      </div>
    </>
  );
}

function ItemForm({
  onSubmit,
  onCancel,
  pending,
}: {
  onSubmit: (body: BudgetItemInput) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("production");
  const [label, setLabel] = useState("");
  const [planned, setPlanned] = useState("");
  const [actual, setActual] = useState("");

  const submit = () => {
    const plannedAmount = parseFloat(planned);
    if (!label.trim() || Number.isNaN(plannedAmount)) return;
    const actualAmount = actual === "" ? null : parseFloat(actual);
    onSubmit({
      category,
      label: label.trim(),
      planned_amount: plannedAmount,
      actual_amount: Number.isNaN(actualAmount as number) ? null : actualAmount,
    });
  };

  return (
    <>
      <div className="form-row">
        <Field label="Category">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as typeof category)}
            style={{
              width: "100%",
              padding: "0.55rem 0.7rem",
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--fg)",
              fontSize: "0.875rem",
            }}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </Field>
        <Field label="Label">
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Music video" autoFocus />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Planned">
          <Input type="number" min="0" step="0.01" value={planned} onChange={(e) => setPlanned(e.target.value)} />
        </Field>
        <Field label="Actual (optional)">
          <Input type="number" min="0" step="0.01" value={actual} onChange={(e) => setActual(e.target.value)} />
        </Field>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={pending || !label.trim() || !planned}>
          {pending ? "Adding…" : "Add item"}
        </Button>
      </div>
    </>
  );
}
