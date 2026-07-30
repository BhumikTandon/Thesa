from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Runtime connection: use the non-superuser `thesa_app` role so RLS binds
    # (superusers and table owners can bypass policies).
    database_url: str = "postgresql+asyncpg://thesa_app@localhost:5432/thesa"

    # Privileged connection for schema bootstrap/migrations only. Falls back
    # to database_url if unset.
    database_admin_url: str | None = None

    clerk_secret_key: str

    # Explicit CORS allowlist for the Command Center web app (no wildcards,
    # credentials disallowed; auth is bearer-token only).
    frontend_origin: str = "http://localhost:3000"

    # HMAC secret for the JIT webhook receiver. Required in any environment
    # that accepts /webhooks/jit. Dev default is fine for local only — rotate
    # via secrets manager before any real issuer traffic.
    webhook_hmac_secret: str = "dev-webhook-hmac-change-me"

    # Reject webhook events whose timestamp is older/newer than this window.
    webhook_timestamp_skew_seconds: int = 300

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @property
    def admin_url(self) -> str:
        return self.database_admin_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
