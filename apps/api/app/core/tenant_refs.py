"""Validation helpers for references between tenant-owned records."""
from __future__ import annotations

from fastapi import HTTPException, status

from app.core.deps import WorkspaceContext


def validate_workspace_reference(
    ctx: WorkspaceContext,
    *,
    table: str,
    reference_id: str,
    resource: str,
) -> None:
    """Require a referenced row to belong to the active workspace."""
    row = (
        ctx.db.table(table)
        .select("id")
        .eq("id", reference_id)
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": f"invalid_{resource}",
                    "message": f"{resource.replace('_', ' ')} must belong to this workspace",
                }
            },
        )


def validate_project_reference(ctx: WorkspaceContext, project_id: str) -> None:
    validate_workspace_reference(
        ctx,
        table="projects",
        reference_id=project_id,
        resource="project",
    )
