"use client";

import Link from "next/link";
import { useState } from "react";

import { useNotificationMutations, useNotifications } from "@/lib/queries/useNotifications";

function relativeTime(value: string) {
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  return formatter.format(Math.round(hours / 24), "day");
}

export function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const notifications = useNotifications(8);
  const mutations = useNotificationMutations();
  const items = notifications.data?.items ?? [];
  const unread = notifications.data?.unread_count ?? 0;

  return (
    <div className="notification-bell-wrap">
      <button className="notification-bell" aria-label={`${unread} unread notifications`} onClick={() => setOpen((value) => !value)}>
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
        </svg>
        {unread > 0 && <span className="notification-count">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="notification-popover glass">
          <div className="notification-popover-head">
            <strong>Notifications</strong>
            {unread > 0 && <button onClick={() => mutations.markAllRead.mutate()}>Mark all read</button>}
          </div>
          <div className="notification-popover-list">
            {notifications.isLoading && <p>Loading notifications…</p>}
            {!notifications.isLoading && items.length === 0 && <p>You’re all caught up.</p>}
            {items.map((item) => (
              <Link
                key={item.id}
                href={item.action_url ?? "/notifications"}
                className={`notification-item${item.read_at ? "" : " unread"}`}
                onClick={() => {
                  if (!item.read_at) mutations.markRead.mutate(item.id);
                  setOpen(false);
                }}
              >
                <span className="notification-dot" />
                <span><strong>{item.title}</strong><small>{item.message}</small><time>{relativeTime(item.created_at)}</time></span>
              </Link>
            ))}
          </div>
          <Link href="/notifications" className="notification-view-all" onClick={() => setOpen(false)}>View all notifications</Link>
        </div>
      )}
    </div>
  );
}
