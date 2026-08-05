"""Environment-driven settings (ARCHITECTURE.md section 1)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    # Service-role key: server-side only, bypasses RLS. Used for the
    # service-owned writes (gravity_scores, ai_outputs) noted in section 2.
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")

    # JWT verification. Supabase signs access tokens with the project JWT
    # secret (HS256) by default; JWKS (RS256) is used for asymmetric keys.
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")
    jwt_audience: str = Field(default="authenticated", alias="SUPABASE_JWT_AUD")

    # CORS — the deployed Next.js origin(s), comma-separated.
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Stripe (placeholder until keys are configured)
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    soundcharts_app_id: str = Field(default="", alias="SOUNDCHARTS_APP_ID")
    soundcharts_api_key: str = Field(default="", alias="SOUNDCHARTS_API_KEY")
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    email_from: str = Field(
        default="Gravity OS <notifications@gravityos.tech>", alias="EMAIL_FROM"
    )
    email_reply_to: str = Field(default="", alias="EMAIL_REPLY_TO")
    super_admin_emails: str = Field(default="", alias="SUPER_ADMIN_EMAILS")
    web_app_url: str = Field(default="http://localhost:3000", alias="WEB_APP_URL")

    environment: str = Field(default="development", alias="ENVIRONMENT")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def super_admin_email_set(self) -> set[str]:
        return {value.strip().lower() for value in self.super_admin_emails.split(",") if value.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
