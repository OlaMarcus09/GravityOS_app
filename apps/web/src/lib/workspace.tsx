"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { useMe } from "@/lib/queries/useMe";
import type { Membership } from "@/lib/api";

// Active-workspace context. Every feature call needs X-Workspace-Id; this holds
// the current selection (persisted to localStorage) and exposes the caller's
// role so pages can hide writer-only actions from viewers.

const STORAGE_KEY = "gravity.workspace_id";

type WorkspaceState = {
  workspaceId: string | null;
  role: Membership["role"] | null;
  plan: string;
  memberships: Membership[];
  isLoading: boolean;
  isReadOnly: boolean;
  setWorkspaceId: (id: string) => void;
};

const Ctx = createContext<WorkspaceState | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useMe();
  const [workspaceId, setWorkspaceIdState] = useState<string | null>(null);

  const memberships = useMemo(() => data?.memberships ?? [], [data]);

  // Resolve the active workspace once memberships load: prefer the stored id if
  // still valid, else fall back to the first membership.
  useEffect(() => {
    if (memberships.length === 0) return;
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    const valid = stored && memberships.some((m) => m.workspace_id === stored);
    setWorkspaceIdState(valid ? stored : memberships[0].workspace_id);
  }, [memberships]);

  const setWorkspaceId = (id: string) => {
    setWorkspaceIdState(id);
    if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, id);
  };

  const role = useMemo(
    () => memberships.find((m) => m.workspace_id === workspaceId)?.role ?? null,
    [memberships, workspaceId],
  );

  const plan = useMemo(
    () => memberships.find((m) => m.workspace_id === workspaceId)?.workspaces?.plan ?? "free",
    [memberships, workspaceId],
  );

  const value: WorkspaceState = {
    workspaceId,
    role,
    plan,
    memberships,
    isLoading,
    isReadOnly: role === "viewer",
    setWorkspaceId,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}

// Convenience: returns the active id or throws — for use inside query/mutation
// functions that require a workspace to be selected.
export function useWorkspaceId(): string | null {
  return useWorkspace().workspaceId;
}
