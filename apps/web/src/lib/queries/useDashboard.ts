"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dashboardApi, gravityScoreApi } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Dashboard aggregate: tasks due/overdue, upcoming events + milestones,
// Gravity Score, and the latest AI output. Keyed by workspace.
export function useDashboard() {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["dashboard", ws],
    queryFn: () => dashboardApi.get(ws!),
    enabled: !!ws,
  });
}

export function useComputeScore() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => gravityScoreApi.compute(ws!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard", ws] }),
  });
}
