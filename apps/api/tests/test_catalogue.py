"""Focused coverage for catalogue storage lifecycle behavior."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.catalogue import create_catalogue_item, delete_catalogue_item
from app.schemas.catalogue import CatalogueItemCreate


def workspace_context(db: Mock) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id="workspace-1",
        role="owner",
        plan="pro",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db,
    )


def fluent_query(*, data: object = None) -> Mock:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.insert.return_value = query
    query.delete.return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def test_create_uses_unique_workspace_scoped_storage_paths() -> None:
    db = Mock()
    query = fluent_query(data=[{"id": "item-1"}])
    db.table.return_value = query
    bucket = Mock()
    bucket.create_signed_upload_url.return_value = {"signedURL": "https://upload.test"}
    service = Mock()
    service.storage.from_.return_value = bucket
    body = CatalogueItemCreate(title="Repeated title", kind="audio")

    with patch("app.routers.catalogue.get_service_client", return_value=service):
        first = create_catalogue_item(body, workspace_context(db))
        second = create_catalogue_item(body, workspace_context(db))

    first_path = bucket.create_signed_upload_url.call_args_list[0].args[0]
    second_path = bucket.create_signed_upload_url.call_args_list[1].args[0]
    assert first_path.startswith("workspace-1/")
    assert second_path.startswith("workspace-1/")
    assert first_path != second_path
    assert first["upload_url"] == "https://upload.test"
    assert second["upload_url"] == "https://upload.test"


def test_delete_removes_storage_object_before_metadata() -> None:
    db = Mock()
    lookup = fluent_query(
        data={"id": "item-1", "workspace_id": "workspace-1", "storage_path": "workspace-1/file-1"}
    )
    deletion = fluent_query(data=[])
    db.table.side_effect = [lookup, deletion]
    bucket = Mock()
    service = Mock()
    service.storage.from_.return_value = bucket

    with patch("app.routers.catalogue.get_service_client", return_value=service):
        delete_catalogue_item("item-1", workspace_context(db))

    service.storage.from_.assert_called_once_with("catalogue")
    bucket.remove.assert_called_once_with(["workspace-1/file-1"])
    deletion.delete.assert_called_once_with()


def test_delete_keeps_metadata_when_storage_removal_fails() -> None:
    db = Mock()
    lookup = fluent_query(
        data={"id": "item-1", "workspace_id": "workspace-1", "storage_path": "workspace-1/file-1"}
    )
    db.table.return_value = lookup
    bucket = Mock()
    bucket.remove.side_effect = RuntimeError("storage unavailable")
    service = Mock()
    service.storage.from_.return_value = bucket

    with patch("app.routers.catalogue.get_service_client", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            delete_catalogue_item("item-1", workspace_context(db))

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error"]["code"] == "storage_delete_failed"
    lookup.delete.assert_not_called()
