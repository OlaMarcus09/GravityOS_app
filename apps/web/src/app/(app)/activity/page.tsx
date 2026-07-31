"use client";

import Link from "next/link";

import { Avatar, Badge, Button, Card, EmptyState, ErrorText, PageHeader, Spinner } from "@/components/ui";
import type { ActivityItem } from "@/lib/api";
import { useActivity } from "@/lib/queries/useCollaboration";

function activityLink(item: ActivityItem) {
  if (!item.target_id) return null;
  if (item.target_type === "project") return `/projects?comments=${item.target_id}`;
  if (item.target_type === "task") return `/tasks?comments=${item.target_id}`;
  return null;
}

function eventLabel(eventType: string) {
  return eventType.replaceAll(".", " ").replaceAll("_", " ");
}

export default function ActivityPage() {
  const query = useActivity();

  return (
    <div>
      <PageHeader title="Activity" subtitle="See what your team has been working on across this workspace." />
      {query.isLoading && <Spinner label="Loading workspace activity…" />}
      <ErrorText error={query.error} />
      {!query.isLoading && query.data?.length === 0 && (
        <EmptyState title="No activity yet" hint="Comments and team updates will appear here." />
      )}
      <div className="activity-list">
        {query.data?.map((item) => {
          const actor = item.actor?.display_name || "A team member";
          const href = activityLink(item);
          return (
            <Card key={item.id} style={{ padding: "1rem 1.1rem" }}>
              <div className="activity-row">
                <Avatar name={actor} src={item.actor?.avatar_url} size={38} />
                <div className="activity-copy">
                  <div className="activity-meta">
                    <strong>{actor}</strong>
                    <Badge>{eventLabel(item.event_type)}</Badge>
                  </div>
                  <p>{item.summary}</p>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
                </div>
                {href && (
                  <Link href={href}>
                    <Button size="sm" variant="ghost">Open</Button>
                  </Link>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
