"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getMe, updateProfile, type ProfileInput } from "@/lib/api";

// TanStack Query hook for the end-to-end /me round-trip.
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: getMe,
  });
}

export function useProfileMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileInput) => updateProfile(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}
