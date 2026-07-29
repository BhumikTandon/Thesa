"""Tenant-isolation and audit-trail verification.

Connects as the non-superuser `thesa_app` role (superusers bypass RLS, so
testing as one proves nothing) and actively attempts cross-tenant access:

    python -m backend.db.verify_isolation

Checks:
  1. Onboarding function creates company + owner atomically.
  2. A tenant session sees its own rows.
  3. Another tenant's session sees NONE of them.
  4. A session with no tenant context sees nothing (fail-closed).
  5. Writing a row for a different company_id is rejected by RLS.
  6. Budget changes appear in audit_log with actor attribution.
  7. audit_log rows cannot be updated (append-only trigger).

Exits non-zero on any failure.
"""

import asyncio
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.config import get_settings

_FAILURES: list[str] = []


def check(condition: bool, name: str) -> None:
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {name}")
    if not condition:
        _FAILURES.append(name)


async def set_tenant(session: AsyncSession, company_id: str, user_id: str | None = None) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant', :t, true)"), {"t": company_id}
    )
    if user_id:
        await session.execute(
            text("SELECT set_config('app.current_user', :u, true)"), {"u": user_id}
        )


async def main() -> None:
    settings = get_settings()
    app_url = make_url(settings.database_url).set(
        username="thesa_app", password=None
    )
    engine = create_async_engine(app_url)
    run_id = uuid.uuid4().hex[:8]

    async with AsyncSession(engine) as session:
        row_a = (
            await session.execute(
                text(
                    "SELECT company_id, user_id FROM create_company_with_owner("
                    ":n, :c, :e)"
                ),
                {"n": f"Acme Concrete {run_id}", "c": f"clerk_a_{run_id}", "e": None},
            )
        ).one()
        row_b = (
            await session.execute(
                text(
                    "SELECT company_id, user_id FROM create_company_with_owner("
                    ":n, :c, :e)"
                ),
                {"n": f"Bravo Roofing {run_id}", "c": f"clerk_b_{run_id}", "e": None},
            )
        ).one()
        await session.commit()
        company_a, owner_a = str(row_a.company_id), str(row_a.user_id)
        company_b = str(row_b.company_id)
        check(company_a != company_b, "onboarding creates two distinct companies")

        resolved = (
            await session.execute(
                text("SELECT role FROM resolve_user(:c)"), {"c": f"clerk_a_{run_id}"}
            )
        ).scalar_one_or_none()
        check(resolved == "owner", "resolve_user returns the owner")

    # Tenant A creates a budget.
    async with AsyncSession(engine) as session:
        await set_tenant(session, company_a, owner_a)
        budget_id = (
            await session.execute(
                text(
                    "INSERT INTO budgets (company_id, name, limit_cents) "
                    "VALUES (:c, :n, 500000) RETURNING id"
                ),
                {"c": company_a, "n": f"Henderson job site {run_id}"},
            )
        ).scalar_one()
        await session.execute(
            text("UPDATE budgets SET limit_cents = 750000 WHERE id = :id"),
            {"id": budget_id},
        )
        await session.commit()

    async with AsyncSession(engine) as session:
        await set_tenant(session, company_a, owner_a)
        own_count = (
            await session.execute(
                text("SELECT count(*) FROM budgets WHERE id = :id"), {"id": budget_id}
            )
        ).scalar_one()
        check(own_count == 1, "tenant A sees its own budget")

        audit_rows = (
            await session.execute(
                text(
                    "SELECT action, actor_user_id FROM audit_log "
                    "WHERE table_name = 'budgets' AND row_id = :id ORDER BY id"
                ),
                {"id": budget_id},
            )
        ).all()
        actions = [r.action for r in audit_rows]
        check(
            actions == ["INSERT", "UPDATE"],
            "audit_log captured budget INSERT and UPDATE",
        )
        check(
            all(r.actor_user_id == owner_a for r in audit_rows),
            "audit rows attribute the acting user",
        )

        audit_id = (
            await session.execute(
                text("SELECT id FROM audit_log WHERE row_id = :id LIMIT 1"),
                {"id": budget_id},
            )
        ).scalar_one()
        try:
            await session.execute(
                text("UPDATE audit_log SET action = 'TAMPERED' WHERE id = :id"),
                {"id": audit_id},
            )
            check(False, "audit_log rejects UPDATE (append-only)")
        except (DBAPIError, ProgrammingError):
            check(True, "audit_log rejects UPDATE (append-only)")
        await session.rollback()

    # Tenant B must see nothing of tenant A's.
    async with AsyncSession(engine) as session:
        await set_tenant(session, company_b)
        cross_count = (
            await session.execute(
                text("SELECT count(*) FROM budgets WHERE id = :id"), {"id": budget_id}
            )
        ).scalar_one()
        check(cross_count == 0, "tenant B cannot see tenant A's budget")

        try:
            await session.execute(
                text(
                    "INSERT INTO budgets (company_id, name, limit_cents) "
                    "VALUES (:c, 'forged', 100)"
                ),
                {"c": company_a},
            )
            check(False, "tenant B cannot write rows for tenant A")
        except (DBAPIError, ProgrammingError):
            check(True, "tenant B cannot write rows for tenant A")
        await session.rollback()

    # No tenant context at all: fail closed.
    async with AsyncSession(engine) as session:
        blind_count = (
            await session.execute(text("SELECT count(*) FROM budgets"))
        ).scalar_one()
        check(blind_count == 0, "no tenant context reads zero rows (fail-closed)")

    await engine.dispose()

    if _FAILURES:
        print(f"\n{len(_FAILURES)} check(s) FAILED")
        sys.exit(1)
    print("\nAll isolation and audit checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
