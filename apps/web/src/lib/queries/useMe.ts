"use client";

import { useQuery } from "@tanstack/react-query";

import { getMe } from "@/lib/api";

// TanStack Query hook for the end-to-end /me round-trip.
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: getMe,
  });
}
