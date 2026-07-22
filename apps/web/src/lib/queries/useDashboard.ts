"use client";

import { useQuery } from "@tanstack/react-query";

import { dashboardApi } from "@/lib/api";
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
