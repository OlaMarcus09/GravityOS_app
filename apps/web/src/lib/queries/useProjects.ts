"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { projectsApi, type ProjectInput } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Query + mutation hooks for projects, keyed by workspace.

export function useProjects() {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["projects", ws],
    queryFn: () => projectsApi.list(ws!),
    enabled: !!ws,
  });
}

export function useProject(id: string | undefined) {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["projects", ws, id],
    queryFn: () => projectsApi.get(ws!, id!),
    enabled: !!ws && !!id,
  });
}

export function useProjectMutations() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["projects", ws] });

  const create = useMutation({
    mutationFn: (body: ProjectInput) => projectsApi.create(ws!, body),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ProjectInput> }) =>
      projectsApi.update(ws!, id, body),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => projectsApi.remove(ws!, id),
    onSuccess: invalidate,
  });

  return { create, update, remove };
}
