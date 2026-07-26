"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar, GravityMark } from "@/components/ui";
import { useMe } from "@/lib/queries/useMe";
import { supabase } from "@/lib/supabase";
import { useWorkspace } from "@/lib/workspace";

// Minimal inline icon set (stroke icons) so the nav rail matches the mockup
// without pulling in an icon dependency.
function Icon({ path, size = 18 }: { path: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={path} />
    </svg>
  );
}

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z" },
  { href: "/calendar", label: "Calendar", icon: "M8 2v4M16 2v4M3 10h18M5 6h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z" },
  { href: "/tasks", label: "Tasks", icon: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" },
  { href: "/projects", label: "Projects", icon: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 0v20M2 12h20" },
  { href: "/catalogue", label: "Vault", icon: "M4 4h16v16H4zM4 9h16M9 9v11" },
  { href: "/budget", label: "Finance", icon: "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" },
  { href: "/marketing", label: "Marketing", icon: "M3 11l18-5v12L3 14v-3ZM11.6 16.8a3 3 0 1 1-5.8-1.6" },
  { href: "/settings", label: "Settings", icon: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" },
];

const SIDEBAR_KEY = "gravity.sidebar_collapsed";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  });
  const { memberships, workspaceId, setWorkspaceId } = useWorkspace();
  const { data: me } = useMe();

  const toggleSidebar = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
      } else {
        setReady(true);
      }
    });
  }, [router]);

  if (!ready) {
    return (
      <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", color: "var(--muted)" }}>
        Entering orbit…
      </main>
    );
  }

  const displayName = me?.profile?.display_name ?? me?.email ?? "You";
  const role = memberships.find((m) => m.workspace_id === workspaceId)?.role;

  const signOut = async () => {
    await supabase.auth.signOut();
    router.replace("/login");
  };

  return (
    <div className="app-shell">
      <aside
        className="glass app-sidebar"
        style={{
          width: collapsed ? 64 : 232,
          borderRadius: 0,
          borderTop: "none",
          borderBottom: "none",
          borderLeft: "none",
          padding: collapsed ? "1.5rem 0.5rem" : "1.5rem 0.9rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
          position: "sticky",
          top: 0,
          height: "100vh",
          transition: "width 200ms ease, padding 200ms ease",
          overflow: "hidden",
        }}
      >
        {/* Brand + collapse toggle */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "space-between", padding: collapsed ? "0" : "0 0.4rem", marginBottom: "1.5rem", minHeight: 26 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.55rem", overflow: "hidden" }}>
            <GravityMark size={26} />
            {!collapsed && (
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, letterSpacing: "-0.01em", whiteSpace: "nowrap" }}>
                Gravity OS
              </span>
            )}
          </div>
          {!collapsed && (
            <button
              onClick={toggleSidebar}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
                padding: "0.2rem",
                display: "flex",
                alignItems: "center",
                flexShrink: 0,
              }}
            >
              <Icon path="M15 18l-6-6 6-6" size={16} />
            </button>
          )}
        </div>

        {/* Expand button when collapsed */}
        {collapsed && (
          <button
            onClick={toggleSidebar}
            aria-label="Expand sidebar"
            title="Expand sidebar"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--muted)",
              cursor: "pointer",
              padding: "0.4rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "0.5rem",
            }}
          >
            <Icon path="M9 18l6-6-6-6" size={16} />
          </button>
        )}

        {/* Workspace switcher — hidden when collapsed */}
        {!collapsed && memberships.length > 1 && (
          <select
            value={workspaceId ?? ""}
            onChange={(e) => setWorkspaceId(e.target.value)}
            style={{
              marginBottom: "1rem",
              padding: "0.45rem 0.55rem",
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--fg)",
              fontSize: "0.8rem",
            }}
          >
            {memberships.map((m) => (
              <option key={m.workspace_id} value={m.workspace_id}>
                {m.workspaces?.name ?? m.workspace_id}
              </option>
            ))}
          </select>
        )}

        <nav style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: collapsed ? "center" : "flex-start",
                  gap: "0.7rem",
                  color: active ? "var(--fg)" : "var(--muted)",
                  background: active ? "var(--accent-soft)" : "transparent",
                  boxShadow: active ? "inset 2px 0 0 var(--accent)" : "none",
                  padding: collapsed ? "0.55rem" : "0.55rem 0.7rem",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "0.875rem",
                  fontWeight: active ? 600 : 500,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                }}
              >
                <span style={{ color: active ? "var(--accent)" : "var(--muted-2)", flexShrink: 0 }}>
                  <Icon path={item.icon} />
                </span>
                {!collapsed && item.label}
              </Link>
            );
          })}
        </nav>

        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {/* User card */}
          {collapsed ? (
            <div style={{ display: "flex", justifyContent: "center" }}>
              <Avatar name={displayName} src={me?.profile?.avatar_url} size={30} />
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                padding: "0.6rem",
                borderRadius: "var(--radius-sm)",
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
              }}
            >
              <Avatar name={displayName} src={me?.profile?.avatar_url} size={30} />
              <div style={{ overflow: "hidden" }}>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>
                  {displayName}
                </div>
                {role && <div style={{ fontSize: "0.68rem", color: "var(--muted-2)", textTransform: "capitalize" }}>{role}</div>}
              </div>
            </div>
          )}
          <button
            onClick={signOut}
            title="Sign out"
            style={{
              background: "transparent",
              border: "1px solid var(--border-strong)",
              color: "var(--muted)",
              padding: collapsed ? "0.45rem" : "0.45rem 0.65rem",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.8rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
              overflow: "hidden",
            }}
          >
            {collapsed ? <Icon path="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" size={16} /> : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="app-content">
        {/* Mobile-only top bar — carries brand, workspace switcher, sign-out. */}
        <header className="mobile-topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", minWidth: 0 }}>
            <GravityMark size={22} />
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "0.95rem", whiteSpace: "nowrap" }}>
              Gravity OS
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", minWidth: 0 }}>
            {memberships.length > 1 && (
              <select
                value={workspaceId ?? ""}
                onChange={(e) => setWorkspaceId(e.target.value)}
                style={{
                  maxWidth: 130,
                  padding: "0.35rem 0.4rem",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--fg)",
                  fontSize: "0.75rem",
                }}
              >
                {memberships.map((m) => (
                  <option key={m.workspace_id} value={m.workspace_id}>
                    {m.workspaces?.name ?? m.workspace_id}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={signOut}
              aria-label="Sign out"
              style={{
                background: "transparent",
                border: "1px solid var(--border-strong)",
                color: "var(--muted)",
                padding: "0.35rem 0.6rem",
                borderRadius: "var(--radius-sm)",
                fontSize: "0.75rem",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="app-main">{children}</main>
      </div>

      {/* Mobile-only bottom tab bar — 7 icon tabs, active tab shows its label. */}
      <nav className="mobile-tabbar">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link key={item.href} href={item.href} className={`tab-item${active ? " active" : ""}`}>
              <Icon path={item.icon} size={20} />
              {active && <span className="tab-label">{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
