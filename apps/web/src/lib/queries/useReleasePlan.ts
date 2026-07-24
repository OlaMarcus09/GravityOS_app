"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  releasesApi,
  type MilestoneInput,
  type ReleasePlan,
  type ReleasePlanInput,
} from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Release-plan query + mutation hooks, scoped to a single project. The GET
// 404s when no plan exists yet, which we surface as null rather than an error.

export function useReleasePlan(projectId: string) {
  const ws = useWorkspaceId();
  return useQuery<ReleasePlan | null>({
    queryKey: ["release-plan", ws, projectId],
    queryFn: async () => {
      try {
        return await releasesApi.get(ws!, projectId);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    enabled: !!ws && !!projectId,
  });
}

export function useReleasePlanMutations(projectId: string) {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["release-plan", ws, projectId] });
    qc.invalidateQueries({ queryKey: ["calendar", ws] });
  };

  const createPlan = useMutation({
    mutationFn: (body: ReleasePlanInput) => releasesApi.create(ws!, projectId, body),
    onSuccess: invalidate,
  });
  const updatePlan = useMutation({
    mutationFn: ({ planId, body }: { planId: string; body: Partial<ReleasePlanInput> }) =>
      releasesApi.update(ws!, planId, body),
    onSuccess: invalidate,
  });
  const addMilestone = useMutation({
    mutationFn: ({ planId, body }: { planId: string; body: MilestoneInput }) =>
      releasesApi.addMilestone(ws!, planId, body),
    onSuccess: invalidate,
  });
  const updateMilestone = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<MilestoneInput> }) =>
      releasesApi.updateMilestone(ws!, id, body),
    onSuccess: invalidate,
  });
  const removeMilestone = useMutation({
    mutationFn: (id: string) => releasesApi.removeMilestone(ws!, id),
    onSuccess: invalidate,
  });

  return { createPlan, updatePlan, addMilestone, updateMilestone, removeMilestone };
}
