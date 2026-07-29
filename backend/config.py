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

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @property
    def admin_url(self) -> str:
        return self.database_admin_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
