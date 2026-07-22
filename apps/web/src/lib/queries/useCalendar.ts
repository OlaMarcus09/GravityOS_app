"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { calendarApi, type EventInput } from "@/lib/api";
import { useWorkspaceId } from "@/lib/workspace";

// Calendar query + mutation hooks. The range query is keyed by the from/to
// window so navigating months refetches cleanly.

export function useCalendar(from?: string, to?: string) {
  const ws = useWorkspaceId();
  return useQuery({
    queryKey: ["calendar", ws, from ?? null, to ?? null],
    queryFn: () => calendarApi.range(ws!, from, to),
    enabled: !!ws,
  });
}

export function useCalendarMutations() {
  const ws = useWorkspaceId();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["calendar", ws] });

  const create = useMutation({
    mutationFn: (body: EventInput) => calendarApi.create(ws!, body),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<EventInput> }) =>
      calendarApi.update(ws!, id, body),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => calendarApi.remove(ws!, id),
    onSuccess: invalidate,
  });

  return { create, update, remove };
}
