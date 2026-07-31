"""Tenant-owned foreign-key references cannot cross workspace boundaries."""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.marketing import create_campaign
from app.routers.releases import create_release_plan
from app.routers.tasks import create_task
from app.schemas.marketing import CampaignCreate
from app.schemas.releases import ReleasePlanCreate
from app.schemas.tasks import TaskCreate

PROJECT_ID = "00000000-0000-0000-0000-000000000010"


def _missing_reference_db() -> tuple[Mock, Mock]:
    query = Mock()
    for method in ("select", "eq", "maybe_single", "insert"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=None)
    db = Mock()
    db.table.return_value = query
    return db, query


def _context(db: Mock) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id="workspace-1",
        role="member",
        plan="team",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db,
    )


@pytest.mark.parametrize(
    ("mutation", "body"),
    [
        (create_task, TaskCreate(title="Launch", project_id=PROJECT_ID)),
        (
            create_campaign,
            CampaignCreate(
                name="Launch",
                objective="awareness",
                start_date="2026-08-01",
                end_date="2026-08-31",
                project_id=PROJECT_ID,
            ),
        ),
    ],
)
def test_create_rejects_project_from_another_workspace(mutation, body):
    db, query = _missing_reference_db()

    with pytest.raises(HTTPException) as exc_info:
        mutation(body, _context(db))

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "invalid_project"
    query.insert.assert_not_called()


def test_release_plan_rejects_project_from_another_workspace():
    db, query = _missing_reference_db()

    with pytest.raises(HTTPException) as exc_info:
        create_release_plan(
            PROJECT_ID,
            ReleasePlanCreate(release_date="2026-08-31"),
            _context(db),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "invalid_project"
    query.insert.assert_not_called()
