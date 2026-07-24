"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { marketingApi, type CampaignInput, type ContentInput } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Marketing query + mutation hooks. Content pieces are nested under campaigns,
// so content mutations invalidate the whole campaigns key.

export function useCampaigns() {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["campaigns", ws],
    queryFn: () => marketingApi.list(ws!),
    enabled: !!ws,
  });
}

export function useMarketingMutations() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["campaigns", ws] });
    qc.invalidateQueries({ queryKey: ["calendar", ws] });
  };

  const create = useMutation({
    mutationFn: (body: CampaignInput) => marketingApi.create(ws!, body),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<CampaignInput> }) =>
      marketingApi.update(ws!, id, body),
    onSuccess: invalidate,
  });
  const addContent = useMutation({
    mutationFn: ({ campaignId, body }: { campaignId: string; body: ContentInput }) =>
      marketingApi.addContent(ws!, campaignId, body),
    onSuccess: invalidate,
  });
  const updateContent = useMutation({
    mutationFn: ({ contentId, body }: { contentId: string; body: Partial<ContentInput> }) =>
      marketingApi.updateContent(ws!, contentId, body),
    onSuccess: invalidate,
  });
  const removeContent = useMutation({
    mutationFn: (contentId: string) => marketingApi.removeContent(ws!, contentId),
    onSuccess: invalidate,
  });

  return { create, update, addContent, updateContent, removeContent };
}
