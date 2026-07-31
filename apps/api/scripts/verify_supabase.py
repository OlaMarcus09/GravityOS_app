#!/usr/bin/env python3
"""Verify a deployed Gravity OS API against a real Supabase project.

Safe by default: without ``--live`` this only prints the checks. Live mode
requires an existing test user's credentials and ``--mutate`` to exercise
create/update/delete paths. Created records are removed in a finally block.

Environment variables (or equivalent CLI flags):
  SUPABASE_URL, SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL/API_URL,
  GRAVITY_TEST_EMAIL, GRAVITY_TEST_PASSWORD
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import httpx


def env(name: str, *fallbacks: str) -> str | None:
    for key in (name, *fallbacks):
        value = os.getenv(key)
        if value:
            return value
    return None


def require(value: str | None, name: str) -> str:
    if not value:
        raise SystemExit(f"Missing {name}; see --help")
    return value


def auth_token(supabase_url: str, anon_key: str, email: str, password: str) -> str:
    response = httpx.post(
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase sign-in failed ({response.status_code}): {response.text}")
    return response.json()["access_token"]


class Api:
    def __init__(self, base: str, token: str, workspace_id: str | None = None):
        self.client = httpx.Client(
            base_url=base.rstrip("/") + "/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        self.workspace_id = workspace_id

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        if self.workspace_id:
            headers["X-Workspace-Id"] = self.workspace_id
        response = self.client.request(method, path, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} failed ({response.status_code}): {response.text}")
        return response.json() if response.content else None

    def expect_status(self, method: str, path: str, status: int) -> None:
        headers = {"X-Workspace-Id": self.workspace_id} if self.workspace_id else {}
        response = self.client.request(method, path, headers=headers)
        if response.status_code != status:
            raise RuntimeError(
                f"{method} {path} returned {response.status_code}; expected {status}: {response.text}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="run authenticated checks")
    parser.add_argument("--mutate", action="store_true", help="also exercise CRUD and cleanup paths")
    parser.add_argument("--api-url", help="FastAPI origin (defaults to API_URL/NEXT_PUBLIC_API_URL)")
    args = parser.parse_args()

    checks = [
        "Supabase password authentication",
        "GET /me and profile/workspace provisioning",
        "workspace membership and tenant header enforcement",
        "dashboard aggregation",
        "Gravity Score read and compute persistence (compute requires --mutate)",
        "project/task/calendar CRUD (requires --mutate)",
    ]
    if not args.live:
        print("Dry run — no network calls or data changes.")
        print("Checks to run:")
        for check in checks:
            print(f"  - {check}")
        print("\nRun with --live for read checks, or --live --mutate for the full workflow.")
        return 0

    supabase_url = require(env("SUPABASE_URL"), "SUPABASE_URL")
    anon_key = require(env("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"), "SUPABASE_ANON_KEY")
    email = require(env("GRAVITY_TEST_EMAIL"), "GRAVITY_TEST_EMAIL")
    password = require(env("GRAVITY_TEST_PASSWORD"), "GRAVITY_TEST_PASSWORD")
    api_url = require(args.api_url or env("API_URL", "NEXT_PUBLIC_API_URL"), "API_URL")

    token = auth_token(supabase_url, anon_key, email, password)
    api = Api(api_url, token)
    me = api.request("GET", "/me")
    memberships = me.get("memberships") or []
    if not memberships:
        raise RuntimeError("Account has no workspace membership; signup trigger/provisioning is broken")
    workspace_id = memberships[0]["workspace_id"]
    api.workspace_id = workspace_id
    api.request("GET", f"/workspaces/{workspace_id}")
    api.request("GET", "/dashboard")
    api.request("GET", "/gravity-score")
    original_workspace_id = api.workspace_id
    api.workspace_id = "00000000-0000-0000-0000-000000000000"
    api.expect_status("GET", "/dashboard", 403)
    api.workspace_id = original_workspace_id
    print(f"PASS read/auth/RLS checks ({workspace_id})")

    if not args.mutate:
        print("PASS (read-only mode; score computation and CRUD skipped)")
        return 0

    created: list[tuple[str, str]] = []
    try:
        score = api.request("POST", "/gravity-score/compute")
        if not score or score.get("workspace_id") != workspace_id:
            raise RuntimeError("Gravity Score did not persist for the active workspace")
        print("PASS Gravity Score computation/persistence")
        project = api.request("POST", "/projects", json={"title": "Verification project"})
        created.append(("/projects", project["id"]))
        task = api.request("POST", "/tasks", json={"title": "Verification task", "project_id": project["id"]})
        created.append(("/tasks", task["id"]))
        event = api.request("POST", "/calendar/events", json={"title": "Verification event", "type": "meeting", "starts_at": "2030-01-01T10:00:00Z"})
        created.append(("/calendar/events", event["id"]))
        api.request("PATCH", f"/tasks/{task['id']}", json={"status": "done"})
        api.request("GET", "/projects")
        api.request("GET", "/tasks")
        api.request("GET", "/calendar")
        print("PASS project/task/calendar CRUD checks")
    finally:
        for collection, item_id in reversed(created):
            try:
                api.request("DELETE", f"{collection}/{item_id}")
            except RuntimeError as exc:
                print(f"WARNING cleanup failed for {collection}/{item_id}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
