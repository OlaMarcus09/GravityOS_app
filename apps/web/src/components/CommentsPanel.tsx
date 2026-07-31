"use client";

import { useMemo, useState } from "react";

import { Avatar, Button, EmptyState, ErrorText, Spinner, Textarea } from "@/components/ui";
import type { CollaborationTarget, WorkspaceMember } from "@/lib/api";
import { useComments, useCommentMutations } from "@/lib/queries/useCollaboration";
import { useMe } from "@/lib/queries/useMe";
import { useTeamMembers } from "@/lib/queries/useTeam";
import { useWorkspace } from "@/lib/workspace";

function memberName(member: WorkspaceMember) {
  return member.profiles?.display_name?.trim() || "Team member";
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function displayBody(value: string) {
  return value.replace(/@\[([^\]\r\n]+)\]\([0-9a-fA-F-]{36}\)/g, "@$1");
}

export function CommentsPanel({ targetType, targetId }: { targetType: CollaborationTarget; targetId: string }) {
  const { workspaceId, role, isReadOnly } = useWorkspace();
  const { data: me } = useMe();
  const comments = useComments(targetType, targetId);
  const mutations = useCommentMutations(targetType, targetId);
  const members = useTeamMembers(workspaceId);
  const [body, setBody] = useState("");
  const [showMentions, setShowMentions] = useState(false);

  const mentionable = useMemo(
    () => (members.data ?? []).filter((member) => member.user_id !== me?.user_id),
    [members.data, me?.user_id],
  );

  const insertMention = (member: WorkspaceMember) => {
    const mention = `@[${memberName(member)}](${member.user_id})`;
    setBody((value) => `${value}${value && !value.endsWith(" ") ? " " : ""}${mention} `);
    setShowMentions(false);
  };

  const submit = () => {
    const content = body.trim();
    if (!content) return;
    mutations.create.mutate(content, { onSuccess: () => setBody("") });
  };

  return (
    <div className="comments-panel">
      {!isReadOnly && (
        <div className="comment-composer">
          <Textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="Share an update or mention a teammate…"
            rows={3}
          />
          <div className="comment-composer-actions">
            <div className="mention-picker-wrap">
              <Button size="sm" variant="ghost" onClick={() => setShowMentions((open) => !open)} disabled={!mentionable.length}>
                @ Mention
              </Button>
              {showMentions && (
                <div className="mention-picker glass">
                  {mentionable.map((member) => (
                    <button key={member.user_id} type="button" onClick={() => insertMention(member)}>
                      <Avatar name={memberName(member)} src={member.profiles?.avatar_url} size={26} />
                      <span>{memberName(member)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Button size="sm" onClick={submit} disabled={!body.trim() || mutations.create.isPending}>
              {mutations.create.isPending ? "Posting…" : "Post comment"}
            </Button>
          </div>
          <ErrorText error={mutations.create.error} />
        </div>
      )}

      {comments.isLoading && <Spinner label="Loading conversation…" />}
      <ErrorText error={comments.error} />
      {!comments.isLoading && comments.data?.length === 0 && (
        <EmptyState title="No comments yet" hint="Start the conversation with your team." />
      )}
      <div className="comment-list">
        {comments.data?.map((comment) => {
          const author = comment.author?.display_name || "Team member";
          const canDelete = comment.author_id === me?.user_id || role === "owner" || role === "admin";
          return (
            <article className="comment-row" key={comment.id}>
              <Avatar name={author} src={comment.author?.avatar_url} size={34} />
              <div className="comment-copy">
                <div className="comment-meta">
                  <strong>{author}</strong>
                  <time dateTime={comment.created_at}>{formatTime(comment.created_at)}</time>
                </div>
                <p>{displayBody(comment.body)}</p>
                {canDelete && (
                  <button type="button" className="comment-delete" onClick={() => mutations.remove.mutate(comment.id)}>
                    Delete
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
