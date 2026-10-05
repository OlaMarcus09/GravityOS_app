from __future__ import annotations

from unittest.mock import Mock

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.marketing import update_campaign, update_content
from app.schemas.marketing import CampaignUpdate, ContentPieceUpdate


def _context(db: Mock) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id="workspace-1",
        role="owner",
        plan="pro",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db,
    )


def _query(data) -> Mock:
    query = Mock()
    for method in ("select", "eq", "maybe_single", "update"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def test_update_campaign_is_workspace_scoped() -> None:
    lookup = _query({"id": "campaign-1", "workspace_id": "workspace-1"})
    updated = _query([{"id": "campaign-1", "status": "active"}])
    db = Mock()
    db.table.side_effect = [lookup, updated]

    result = update_campaign(
        "campaign-1",
        CampaignUpdate(status="active"),
        _context(db),
    )

    assert result["status"] == "active"
    lookup.select.assert_called_once_with("*")
    lookup.eq.assert_any_call("id", "campaign-1")
    lookup.eq.assert_any_call("workspace_id", "workspace-1")
    updated.update.assert_called_once_with({"status": "active"})
    updated.eq.assert_any_call("id", "campaign-1")
    updated.eq.assert_any_call("workspace_id", "workspace-1")


def test_update_content_is_workspace_scoped() -> None:
    lookup = _query({"id": "content-1", "workspace_id": "workspace-1"})
    updated = _query([{"id": "content-1", "caption": "Edited caption", "status": "scheduled"}])
    db = Mock()
    db.table.side_effect = [lookup, updated]

    result = update_content(
        "content-1",
        ContentPieceUpdate(caption="Edited caption", status="scheduled"),
        _context(db),
    )

    assert result["caption"] == "Edited caption"
    lookup.select.assert_called_once_with("*")
    lookup.eq.assert_any_call("id", "content-1")
    lookup.eq.assert_any_call("workspace_id", "workspace-1")
    updated.update.assert_called_once_with({"status": "scheduled", "caption": "Edited caption"})
    updated.eq.assert_any_call("id", "content-1")
    updated.eq.assert_any_call("workspace_id", "workspace-1")
