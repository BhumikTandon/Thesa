"""Budgets: monthly spending envelopes per job site or department.

Managers create and adjust; crew leads can read. Every change is captured by
the immutable audit trigger.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import Budget, Transaction
from backend.schemas import BudgetCreate, BudgetOut, BudgetUpdate

router = APIRouter(prefix="/budgets")


async def _month_spend(session: AsyncSession) -> dict[uuid.UUID, int]:
    """Month-to-date spend per budget for the current tenant (RLS-scoped)."""
    month_start = date.today().replace(day=1)
    rows = (
        await session.execute(
            select(
                Transaction.budget_id,
                func.coalesce(func.sum(Transaction.amount_cents), 0),
            )
            .where(
                Transaction.budget_id.is_not(None),
                Transaction.occurred_on >= month_start,
            )
            .group_by(Transaction.budget_id)
        )
    ).all()
    return {budget_id: int(total) for budget_id, total in rows}


def _to_out(budget: Budget, spent_cents: int) -> BudgetOut:
    return BudgetOut(
        id=budget.id,
        name=budget.name,
        category=budget.category,
        limit_cents=budget.limit_cents,
        active=budget.active,
        spent_cents_this_month=spent_cents,
        remaining_cents=max(0, budget.limit_cents - spent_cents),
        created_at=budget.created_at,
    )


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[BudgetOut]:
    budgets = (await session.execute(select(Budget))).scalars().all()
    spend = await _month_spend(session)
    return [_to_out(b, spend.get(b.id, 0)) for b in budgets]


@router.post(
    "",
    response_model=BudgetOut,
    status_code=201,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def create_budget(
    body: BudgetCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> BudgetOut:
    budget = Budget(
        company_id=uuid.UUID(request.state.company_id),
        name=body.name,
        category=body.category.value if body.category else None,
        limit_cents=body.limit_cents,
    )
    session.add(budget)
    await session.flush()
    return _to_out(budget, 0)


@router.patch(
    "/{budget_id}",
    response_model=BudgetOut,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def update_budget(
    budget_id: uuid.UUID,
    body: BudgetUpdate,
    session: AsyncSession = Depends(get_tenant_session),
) -> BudgetOut:
    budget = (
        await session.execute(select(Budget).where(Budget.id == budget_id))
    ).scalar_one_or_none()
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")

    if body.limit_cents is not None:
        budget.limit_cents = body.limit_cents
    if body.active is not None:
        budget.active = body.active
    await session.flush()

    spend = await _month_spend(session)
    return _to_out(budget, spend.get(budget.id, 0))
