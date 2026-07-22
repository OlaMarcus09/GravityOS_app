"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { catalogueApi, type CatalogueInput } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Catalogue query + mutation hooks. Create returns a signed upload_url and get
// returns a signed download_url; the page drives the file PUT/GET with those.

export function useCatalogue(params?: Record<string, string>) {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["catalogue", ws, params ?? {}],
    queryFn: () => catalogueApi.list(ws!, params),
    enabled: !!ws,
  });
}

export function useCatalogueMutations() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["catalogue", ws] });

  const create = useMutation({
    mutationFn: (body: CatalogueInput) => catalogueApi.create(ws!, body),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<CatalogueInput> }) =>
      catalogueApi.update(ws!, id, body),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => catalogueApi.remove(ws!, id),
    onSuccess: invalidate,
  });

  return { create, update, remove };
}
