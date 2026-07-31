"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { teamApi, type WorkspaceMember } from "@/lib/api";

export function useTeamMembers(workspaceId: string | null) {
  return useQuery({
    queryKey: ["team", "members", workspaceId],
    queryFn: () => teamApi.members(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useTeamMemberMutations(workspaceId: string | null) {
  const queryClient = useQueryClient();
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["team", "members", workspaceId] });
    queryClient.invalidateQueries({ queryKey: ["me"] });
  };
  return {
    update: useMutation({
      mutationFn: ({ userId, role }: { userId: string; role: WorkspaceMember["role"] }) =>
        teamApi.updateMember(workspaceId!, userId, role),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (userId: string) => teamApi.removeMember(workspaceId!, userId),
      onSuccess: refresh,
    }),
  };
}
