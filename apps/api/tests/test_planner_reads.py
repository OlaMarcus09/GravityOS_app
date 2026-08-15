from __future__ import annotations

from unittest.mock import Mock

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.marketing import list_campaigns
from app.routers.releases import get_release_plan


def _context(db: Mock) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id="workspace-1",
        role="owner",
        plan="team",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db,
    )


def _query(data) -> Mock:
    query = Mock()
    for method in ("select", "eq", "order", "maybe_single"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def test_campaign_list_includes_nested_content_pieces() -> None:
    rows = [{"id": "campaign-1", "content_pieces": [{"id": "content-1"}]}]
    query = _query(rows)
    db = Mock()
    db.table.return_value = query

    assert list_campaigns(ctx=_context(db), project_id=None, status_filter=None) == rows
    query.select.assert_called_once_with("*, content_pieces(*)")
    query.eq.assert_called_once_with("workspace_id", "workspace-1")


def test_release_plan_read_includes_nested_milestones() -> None:
    row = {"id": "plan-1", "release_milestones": [{"id": "milestone-1"}]}
    query = _query(row)
    db = Mock()
    db.table.return_value = query

    assert get_release_plan("project-1", _context(db)) == row
    query.select.assert_called_once_with("*, release_milestones(*)")
    query.eq.assert_any_call("project_id", "project-1")
    query.eq.assert_any_call("workspace_id", "workspace-1")
