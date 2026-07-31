"use client";

import Link from "next/link";
import { Button, Card, EmptyState, PageHeader } from "@/components/ui";
import { useNotificationMutations, useNotifications } from "@/lib/queries/useNotifications";

export default function NotificationsPage() {
  const query = useNotifications(100);
  const mutations = useNotificationMutations();
  const items = query.data?.items ?? [];
  return <div>
    <PageHeader title="Notifications" subtitle="Stay on top of workspace activity and important updates."
      action={query.data?.unread_count ? <Button variant="ghost" onClick={() => mutations.markAllRead.mutate()}>Mark all read</Button> : undefined} />
    {query.isLoading && <p style={{ color: "var(--muted)" }}>Loading notifications…</p>}
    {!query.isLoading && items.length === 0 && <EmptyState title="You’re all caught up" hint="New workspace updates will appear here." />}
    <div className="notifications-page-list">{items.map((item) => <Card key={item.id} style={{ padding: "1rem 1.1rem" }}>
      <div className="notification-page-row"><div className="notification-page-copy"><strong>{item.title}</strong><p>{item.message}</p><small>{new Date(item.created_at).toLocaleString()}</small></div>
      <div className="notification-page-actions">{!item.read_at && <Button size="sm" variant="ghost" onClick={() => mutations.markRead.mutate(item.id)}>Mark read</Button>}{item.action_url && <Link href={item.action_url}><Button size="sm">Open</Button></Link>}<Button size="sm" variant="danger" onClick={() => mutations.dismiss.mutate(item.id)}>Dismiss</Button></div></div>
    </Card>)}</div>
  </div>;
}
