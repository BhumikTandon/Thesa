"""Apply the database schema: tables, then RLS policies and audit triggers.

Usage:
    python -m backend.db.bootstrap

Idempotent: tables use CREATE TABLE IF NOT EXISTS semantics via metadata
create_all, and rls.sql uses CREATE OR REPLACE / DROP IF EXISTS throughout.

Note: the role running this script owns the SECURITY DEFINER auth functions
in rls.sql. In development that is typically the local superuser; in
production, run bootstrap as a dedicated migration role with BYPASSRLS and
connect the application as a separate non-superuser role.
"""

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings
from backend.models import Base

_SQL_DIR = Path(__file__).parent
_SQL_FILES = ("rls.sql", "grants.sql")


async def bootstrap() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # The SQL files contain DO $$ blocks and multi-statement scripts, so
        # they are executed through the asyncpg driver's simple-query protocol
        # rather than as individual prepared statements.
        raw = await conn.get_raw_connection()
        for sql_file in _SQL_FILES:
            await raw.driver_connection.execute((_SQL_DIR / sql_file).read_text())

    await engine.dispose()
    print("Schema, RLS policies, audit triggers, and grants applied.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
