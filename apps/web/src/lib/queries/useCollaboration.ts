"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { collaborationApi, type CollaborationTarget } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

export function useComments(targetType: CollaborationTarget, targetId: string | null) {
  const workspaceId = useWorkspaceId();
  return useQuery({
    queryKey: ["collaboration", "comments", workspaceId, targetType, targetId],
    queryFn: () => collaborationApi.comments(workspaceId!, targetType, targetId!),
    enabled: Boolean(workspaceId && targetId),
  });
}

export function useCommentMutations(targetType: CollaborationTarget, targetId: string | null) {
  const workspaceId = useWorkspaceId();
  const queryClient = useQueryClient();
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["collaboration", "comments", workspaceId, targetType, targetId] });
    queryClient.invalidateQueries({ queryKey: ["collaboration", "activity", workspaceId] });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  return {
    create: useMutation({
      mutationFn: (body: string) =>
        collaborationApi.createComment(workspaceId!, {
          target_type: targetType,
          target_id: targetId!,
          body,
        }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => collaborationApi.removeComment(workspaceId!, id),
      onSuccess: refresh,
    }),
  };
}

export function useActivity(limit = 100) {
  const workspaceId = useWorkspaceId();
  return useQuery({
    queryKey: ["collaboration", "activity", workspaceId, limit],
    queryFn: () => collaborationApi.activity(workspaceId!, limit),
    enabled: Boolean(workspaceId),
    refetchInterval: 30_000,
  });
}
