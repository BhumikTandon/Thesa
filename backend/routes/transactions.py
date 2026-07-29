"""Transactions: manual purchase entry and listing.

Manual entry seeds the Reward Router with spend history until the Marqeta
transaction feed lands. Category is auto-classified from the merchant name
when not supplied.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.models import Budget, PortfolioCard, Transaction
from backend.schemas import TransactionCreate, TransactionOut
from backend.services.vendor_classifier import classify_merchant

router = APIRouter(prefix="/transactions")


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[TransactionOut]:
    transactions = (
        (
            await session.execute(
                select(Transaction)
                .order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [TransactionOut.model_validate(t, from_attributes=True) for t in transactions]


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> TransactionOut:
    # Referenced rows are fetched through the tenant session, so RLS turns
    # any cross-tenant reference into a 404.
    if body.portfolio_card_id is not None:
        card = (
            await session.execute(
                select(PortfolioCard).where(PortfolioCard.id == body.portfolio_card_id)
            )
        ).scalar_one_or_none()
        if card is None:
            raise HTTPException(status_code=404, detail="Portfolio card not found")

    if body.budget_id is not None:
        budget = (
            await session.execute(select(Budget).where(Budget.id == body.budget_id))
        ).scalar_one_or_none()
        if budget is None:
            raise HTTPException(status_code=404, detail="Budget not found")

    category = body.category or classify_merchant(body.merchant_name)

    transaction = Transaction(
        company_id=uuid.UUID(request.state.company_id),
        user_id=uuid.UUID(request.state.user_id),
        portfolio_card_id=body.portfolio_card_id,
        budget_id=body.budget_id,
        merchant_name=body.merchant_name,
        category=category.value,
        amount_cents=body.amount_cents,
        currency=body.currency,
        occurred_on=body.occurred_on,
    )
    session.add(transaction)
    await session.flush()
    return TransactionOut.model_validate(transaction, from_attributes=True)
