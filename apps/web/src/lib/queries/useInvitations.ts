"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { invitationsApi, type WorkspaceInvitation } from "@/lib/api";

export function usePendingInvitations() {
  return useQuery({ queryKey: ["invitations", "pending"], queryFn: invitationsApi.pending });
}

export function useWorkspaceInvitations(workspaceId: string | null) {
  return useQuery({
    queryKey: ["invitations", workspaceId],
    queryFn: () => invitationsApi.list(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useInvitationMutations(workspaceId: string | null) {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["invitations"] });
    qc.invalidateQueries({ queryKey: ["me"] });
  };
  return {
    create: useMutation({
      mutationFn: (body: { email: string; role: WorkspaceInvitation["role"] }) =>
        invitationsApi.create(workspaceId!, body),
      onSuccess: refresh,
    }),
    accept: useMutation({ mutationFn: invitationsApi.accept, onSuccess: refresh }),
    resend: useMutation({ mutationFn: (id: string) => invitationsApi.resend(workspaceId!, id), onSuccess: refresh }),
    revoke: useMutation({ mutationFn: (id: string) => invitationsApi.revoke(workspaceId!, id), onSuccess: refresh }),
  };
}
