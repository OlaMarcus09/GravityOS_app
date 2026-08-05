"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { notificationsApi } from "@/lib/api";
import type { NotificationPreferencesUpdate } from "@/lib/api";

export function useNotifications(limit = 30) {
  return useQuery({
    queryKey: ["notifications", limit],
    queryFn: () => notificationsApi.list(limit),
    refetchInterval: 30_000,
  });
}

export function useNotificationMutations() {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  return {
    markRead: useMutation({ mutationFn: notificationsApi.markRead, onSuccess: refresh }),
    markAllRead: useMutation({ mutationFn: notificationsApi.markAllRead, onSuccess: refresh }),
    dismiss: useMutation({ mutationFn: notificationsApi.dismiss, onSuccess: refresh }),
  };
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: ["notification-preferences"],
    queryFn: notificationsApi.preferences,
  });
}

export function useNotificationPreferencesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NotificationPreferencesUpdate) => notificationsApi.updatePreferences(body),
    onSuccess: (preferences) => queryClient.setQueryData(["notification-preferences"], preferences),
  });
}
