"""FastAPI app factory (ARCHITECTURE.md section 4).

Mounts every resource router under /api/v1. Only /me is wired end-to-end for
the skeleton; the rest return stub markers behind real dependency chains.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
    budgets,
    calendar,
    catalogue,
    dashboard,
    intelligence,
    marketing,
    me,
    projects,
    releases,
    tasks,
    workspaces,
)

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Gravity OS API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Unauthenticated liveness probe (used by Render health check).
    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "environment": settings.environment}

    v1 = APIRouter(prefix=API_PREFIX)
    for module in (
        me,
        workspaces,
        projects,
        tasks,
        calendar,
        releases,
        catalogue,
        budgets,
        marketing,
        dashboard,
        intelligence,
    ):
        v1.include_router(module.router)
    app.include_router(v1)

    return app


app = create_app()
