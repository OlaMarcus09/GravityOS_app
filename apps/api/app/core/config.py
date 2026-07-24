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

    environment: str = Field(default="development", alias="ENVIRONMENT")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
