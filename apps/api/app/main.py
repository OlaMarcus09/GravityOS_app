"""FastAPI app factory (ARCHITECTURE.md section 4).

Mounts every resource router under /api/v1. Only /me is wired end-to-end for
the skeleton; the rest return stub markers behind real dependency chains.
"""
from __future__ import annotations

from secrets import compare_digest

from fastapi import APIRouter, FastAPI, Header, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import get_service_client
from app.jobs.notifications import run_notification_cycle
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
    streaming,
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

    @app.get("/health/ready", tags=["health"])
    def readiness() -> dict:
        """Confirm the API can reach its primary datastore before serving traffic."""
        required = {
            "SUPABASE_URL": settings.supabase_url,
            "SUPABASE_ANON_KEY": settings.supabase_anon_key,
            "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "configuration_incomplete",
                        "message": "Required backend configuration is missing",
                        "details": {"missing": missing},
                    }
                },
            )
        try:
            get_service_client().table("workspaces").select("id").limit(1).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "database_unavailable",
                        "message": "Primary datastore is unavailable",
                    }
                },
            ) from exc
        return {"status": "ready", "environment": settings.environment}

    @app.post("/internal/notifications/run", include_in_schema=False)
    def run_notifications(
        x_cron_key: str | None = Header(default=None, alias="X-Cron-Key"),
    ) -> dict[str, int]:
        if not settings.notification_cron_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "cron_not_configured",
                        "message": "Notification scheduling is not configured",
                    }
                },
            )
        if not x_cron_key or not compare_digest(x_cron_key, settings.notification_cron_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "invalid_cron_key", "message": "Invalid cron key"}},
            )
        return run_notification_cycle()

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
        streaming,
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
