from __future__ import annotations

from unittest.mock import Mock

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.budgets import update_budget_item
from app.schemas.budgets import BudgetItemUpdate


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


def test_update_budget_item_is_workspace_scoped_and_updates_actual() -> None:
    lookup = _query({"id": "item-1", "budgets": {"workspace_id": "workspace-1"}})
    updated = _query([{"id": "item-1", "actual_amount": "250.00"}])
    db = Mock()
    db.table.side_effect = [lookup, updated]

    result = update_budget_item(
        "item-1",
        BudgetItemUpdate(actual_amount=250),
        _context(db),
    )

    assert result["actual_amount"] == "250.00"
    lookup.select.assert_called_once_with("*, budgets!inner(workspace_id)")
    lookup.eq.assert_any_call("id", "item-1")
    lookup.eq.assert_any_call("budgets.workspace_id", "workspace-1")
    updated.update.assert_called_once_with({"actual_amount": "250"})
    updated.eq.assert_called_once_with("id", "item-1")
