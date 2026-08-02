"use client";

import Link from "next/link";
import { useState } from "react";

import { Avatar, Badge, Button, Card, EmptyState, ErrorText, Field, PageHeader, Select, Spinner } from "@/components/ui";
import type { ActivityEventType, ActivityItem } from "@/lib/api";
import { useActivity } from "@/lib/queries/useCollaboration";
import { useProjects } from "@/lib/queries/useProjects";
import { useTeamMembers } from "@/lib/queries/useTeam";
import { useWorkspaceId } from "@/lib/workspace";

const EVENT_TYPES: { value: ActivityEventType; label: string }[] = [
  { value: "comment.created", label: "Comment added" },
  { value: "comment.deleted", label: "Comment deleted" },
  { value: "project_created", label: "Project created" },
  { value: "project_updated", label: "Project updated" },
  { value: "task_created", label: "Task created" },
  { value: "task_updated", label: "Task updated" },
  { value: "task_submitted_for_approval", label: "Task submitted for approval" },
  { value: "task_approved", label: "Task approved" },
  { value: "task_completed", label: "Task completed" },
  { value: "task_rejected", label: "Task rejected" },
];

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
  const workspaceId = useWorkspaceId();
  const [projectId, setProjectId] = useState("");
  const [memberId, setMemberId] = useState("");
  const [eventType, setEventType] = useState<ActivityEventType | "">("");
  const projects = useProjects();
  const members = useTeamMembers(workspaceId);
  const query = useActivity({
    projectId: projectId || undefined,
    memberId: memberId || undefined,
    eventType: eventType || undefined,
  });
  const hasFilters = Boolean(projectId || memberId || eventType);

  const clearFilters = () => {
    setProjectId("");
    setMemberId("");
    setEventType("");
  };

  return (
    <div>
      <PageHeader title="Activity" subtitle="See what your team has been working on across this workspace." />
      <Card style={{ marginBottom: "1rem" }}>
        <div className="form-row" style={{ alignItems: "flex-end" }}>
          <Field label="Project">
            <Select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">All projects</option>
              {projects.data?.map((project) => (
                <option key={project.id} value={project.id}>{project.title}</option>
              ))}
            </Select>
          </Field>
          <Field label="Team member">
            <Select value={memberId} onChange={(event) => setMemberId(event.target.value)}>
              <option value="">All members</option>
              {members.data?.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {member.profiles?.display_name || "Unnamed member"}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Event type">
            <Select
              value={eventType}
              onChange={(event) => setEventType(event.target.value as ActivityEventType | "")}
            >
              <option value="">All events</option>
              {EVENT_TYPES.map((event) => (
                <option key={event.value} value={event.value}>{event.label}</option>
              ))}
            </Select>
          </Field>
          <Button variant="ghost" onClick={clearFilters} disabled={!hasFilters}>Clear</Button>
        </div>
        <ErrorText error={projects.error || members.error} />
      </Card>
      {query.isLoading && <Spinner label="Loading workspace activity…" />}
      <ErrorText error={query.error} />
      {!query.isLoading && query.data?.length === 0 && (
        <EmptyState
          title={hasFilters ? "No matching activity" : "No activity yet"}
          hint={hasFilters ? "Try changing or clearing the filters." : "Comments and team updates will appear here."}
        />
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
