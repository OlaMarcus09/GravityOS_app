"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { tasksApi, type TaskInput } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Query + mutation hooks for tasks. All keyed by workspace so switching
// workspaces refetches cleanly.

export function useTasks(params?: Record<string, string>) {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["tasks", ws, params ?? {}],
    queryFn: () => tasksApi.list(ws!, params),
    enabled: !!ws,
  });
}

export function useTaskMutations() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tasks", ws] });
    qc.invalidateQueries({ queryKey: ["calendar", ws] });
    qc.invalidateQueries({ queryKey: ["collaboration", "activity", ws] });
  };

  const create = useMutation({
    mutationFn: (body: TaskInput) => tasksApi.create(ws!, body),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<TaskInput> & { completed_at?: string | null } }) =>
      tasksApi.update(ws!, id, body),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => tasksApi.remove(ws!, id),
    onSuccess: invalidate,
  });

  const submitApproval = useMutation({
    mutationFn: (id: string) => tasksApi.submitApproval(ws!, id),
    onSuccess: invalidate,
  });
  const approve = useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => tasksApi.approve(ws!, id, note),
    onSuccess: invalidate,
  });
  const reject = useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => tasksApi.reject(ws!, id, note),
    onSuccess: invalidate,
  });

  return { create, update, remove, submitApproval, approve, reject };
}
