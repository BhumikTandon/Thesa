"""Database session management with RLS tenant context.

Every tenant session executes `SET LOCAL app.current_tenant = :tenant_id`
(and `app.current_user` for audit-trigger attribution) before yielding,
ensuring PostgreSQL Row-Level Security policies can evaluate the current
tenant without any application-layer filtering.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy import text
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


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
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

    Sets `app.current_tenant` (consumed by RLS policies) and
    `app.current_user` (consumed by audit triggers for actor attribution).
    Commits on success, rolls back on exception. `SET LOCAL` is scoped to the
    transaction, so the variables vanish when it ends — fail-closed.
    """
    company_id: str = request.state.company_id
    user_id: str | None = getattr(request.state, "user_id", None)

    factory = get_session_factory(settings)
    async with factory() as session:
        # set_config(..., true) == SET LOCAL, but accepts bind parameters
        # (SET LOCAL itself only takes literals).
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": company_id},
        )
        if user_id is not None:
            await session.execute(
                text("SELECT set_config('app.current_user', :user_id, true)"),
                {"user_id": str(user_id)},
            )

        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def get_plain_session(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    """Session without tenant context, for the onboarding path only.

    RLS policies fail closed with no tenant set, so this session can read
    nothing from tenant tables directly; onboarding goes through the
    SECURITY DEFINER `create_company_with_owner` function.
    """
    factory = get_session_factory(settings)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
