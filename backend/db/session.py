"""Database session management with RLS tenant context.

Every session executes `SET LOCAL app.current_tenant = :tenant_id` before
yielding, ensuring PostgreSQL Row-Level Security policies can evaluate the
current tenant without any application-layer filtering.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings, get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine(settings: Settings):
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_size=20,
            max_overflow=5,
            pool_pre_ping=True,
        )
    return _engine


def _get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = _get_engine(settings)
        _session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_tenant_session(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a tenant-scoped database session.

    Sets the PostgreSQL session variable `app.current_tenant` so that RLS
    policies can enforce row-level isolation without application-layer filters.
    """
    company_id: str = request.state.company_id

    factory = _get_session_factory(settings)
    async with factory() as session:
        await session.execute(
            text("SET LOCAL app.current_tenant = :tenant_id"),
            {"tenant_id": company_id},
        )

        yield session
