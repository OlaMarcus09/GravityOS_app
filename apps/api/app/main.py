"""FastAPI app factory (ARCHITECTURE.md section 4).

Mounts every resource router under /api/v1. Only /me is wired end-to-end for
the skeleton; the rest return stub markers behind real dependency chains.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import (
    billing,
    budgets,
    calendar,
    catalogue,
    collaboration,
    dashboard,
    intelligence,
    marketing,
    me,
    notifications,
    projects,
    releases,
    tasks,
    workspaces,
)

API_PREFIX = "/api/v1"


def _normalize_error(detail: object) -> dict[str, object]:
    """Convert FastAPI and application exceptions to the public error contract."""
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        raw_error = detail["error"]
        code = raw_error.get("code")
        message = raw_error.get("message")
        return {
            "code": code if isinstance(code, str) and code else "http_error",
            "message": message if isinstance(message, str) and message else "Request failed",
            "details": raw_error.get("details"),
        }
    if isinstance(detail, str):
        return {"code": "http_error", "message": detail, "details": None}
    return {"code": "http_error", "message": "Request failed", "details": detail}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Gravity OS API", version="0.1.0")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Expose the documented error shape consistently to the web client."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": _normalize_error(exc.detail)},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )

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
        notifications,
        collaboration,
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
        billing,
    ):
        v1.include_router(module.router)
    app.include_router(v1)

    return app


app = create_app()
