"""Apply schema migrations, then RLS policies and audit triggers.

Usage:
    python -m backend.db.bootstrap

Flow:
  1. `alembic upgrade head` against DATABASE_ADMIN_URL (table DDL)
  2. Apply backend/db/rls.sql and grants.sql (policies, triggers, role)

Idempotent: Alembic no-ops when already at head; rls.sql / grants.sql use
CREATE OR REPLACE / DROP IF EXISTS throughout.

Note: the role running this script owns the SECURITY DEFINER auth functions
in rls.sql. In development that is typically the local superuser; in
production, run bootstrap as a dedicated migration role with BYPASSRLS and
connect the application as a separate non-superuser role.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings

_SQL_DIR = Path(__file__).parent
_SQL_FILES = ("rls.sql", "grants.sql")
_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _ROOT / "alembic.ini"


def _run_alembic_upgrade() -> None:
    # Run in a subprocess so Alembic's own asyncio.run does not nest inside
    # this process's event loop.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(_ALEMBIC_INI),
            "upgrade",
            "head",
        ],
        cwd=str(_ROOT),
        check=True,
    )


async def _apply_rls_and_grants() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_url)

    async with engine.begin() as conn:
        # The SQL files contain DO $$ blocks and multi-statement scripts, so
        # they are executed through the asyncpg driver's simple-query protocol
        # rather than as individual prepared statements.
        raw = await conn.get_raw_connection()
        for sql_file in _SQL_FILES:
            await raw.driver_connection.execute((_SQL_DIR / sql_file).read_text())

    await engine.dispose()


def bootstrap() -> None:
    _run_alembic_upgrade()
    asyncio.run(_apply_rls_and_grants())
    print("Migrations, RLS policies, audit triggers, and grants applied.")


if __name__ == "__main__":
    bootstrap()
