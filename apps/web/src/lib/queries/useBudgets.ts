"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { budgetsApi, type BudgetInput, type BudgetItemInput } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Budget query + mutation hooks. Items are nested under a budget, so item
// mutations invalidate the whole budgets key to refresh the list.

export function useBudgets() {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["budgets", ws],
    queryFn: () => budgetsApi.list(ws!),
    enabled: !!ws,
  });
}

export function useBudgetMutations() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["budgets", ws] });

  const create = useMutation({
    mutationFn: (body: BudgetInput) => budgetsApi.create(ws!, body),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<BudgetInput> }) =>
      budgetsApi.update(ws!, id, body),
    onSuccess: invalidate,
  });
  const addItem = useMutation({
    mutationFn: ({ budgetId, body }: { budgetId: string; body: BudgetItemInput }) =>
      budgetsApi.addItem(ws!, budgetId, body),
    onSuccess: invalidate,
  });
  const updateItem = useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: Partial<BudgetItemInput> }) =>
      budgetsApi.updateItem(ws!, itemId, body),
    onSuccess: invalidate,
  });
  const removeItem = useMutation({
    mutationFn: (itemId: string) => budgetsApi.removeItem(ws!, itemId),
    onSuccess: invalidate,
  });

  return { create, update, addItem, updateItem, removeItem };
}
