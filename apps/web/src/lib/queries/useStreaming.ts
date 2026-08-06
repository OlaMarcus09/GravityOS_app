"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { streamingApi } from "@/lib/api";

export function useArtistStreamingLink(workspaceId: string | null) {
  return useQuery({
    queryKey: ["streaming-link", workspaceId],
    queryFn: () => streamingApi.link(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useStreamingSummary(workspaceId: string | null) {
  return useQuery({
    queryKey: ["streaming-summary", workspaceId],
    queryFn: () => streamingApi.summary(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useStreamingMutations(workspaceId: string | null) {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["streaming-link", workspaceId] }),
      queryClient.invalidateQueries({ queryKey: ["streaming-summary", workspaceId] }),
    ]);
  };
  return {
    connect: useMutation({
      mutationFn: (soundchartsUuid: string) => streamingApi.connect(workspaceId!, soundchartsUuid),
      onSuccess: refresh,
    }),
    disconnect: useMutation({
      mutationFn: (linkId: string) => streamingApi.disconnect(workspaceId!, linkId),
      onSuccess: refresh,
    }),
    sync: useMutation({
      mutationFn: (linkId: string) => streamingApi.sync(workspaceId!, linkId),
      onSuccess: refresh,
    }),
  };
}
