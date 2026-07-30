"""Card Teller — the authorization decision loop.

Evaluates a JIT funding request against card status, vendor/category scope,
single-tx limit, budget remaining, per diem remaining, and company spend
policies. Fail-closed: any uncertainty declines.

Designed to finish well under a 2-second issuer timeout; all work is local DB.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuthDecision,
    Budget,
    IssuedCard,
    IssuedCardStatus,
    PerDiem,
    SpendPolicy,
    Transaction,
)
from backend.services.vendor_classifier import classify_merchant


@dataclass(frozen=True)
class TellerResult:
    decision: AuthDecision
    reason: str
    category: str


async def evaluate_authorization(
    session: AsyncSession,
    *,
    card: IssuedCard,
    merchant_name: str,
    amount_cents: int,
    category: str | None = None,
    now: datetime | None = None,
) -> TellerResult:
    """Run the Card Teller loop. Never raises for policy reasons — declines."""
    now = now or datetime.now(timezone.utc)
    resolved_category = (
        category or classify_merchant(merchant_name).value
    )

    if card.status != IssuedCardStatus.ACTIVE.value:
        return TellerResult(
            AuthDecision.DECLINED, f"card_{card.status}", resolved_category
        )

    if card.expires_at is not None and card.expires_at <= now:
        return TellerResult(
            AuthDecision.DECLINED, "card_expired", resolved_category
        )

    if amount_cents <= 0:
        return TellerResult(
            AuthDecision.DECLINED, "invalid_amount", resolved_category
        )

    if (
        card.single_tx_limit_cents is not None
        and amount_cents > card.single_tx_limit_cents
    ):
        return TellerResult(
            AuthDecision.DECLINED, "over_single_tx_limit", resolved_category
        )

    if card.scoped_vendor:
        if card.scoped_vendor.strip().lower() not in merchant_name.strip().lower():
            return TellerResult(
                AuthDecision.DECLINED, "vendor_mismatch", resolved_category
            )

    if card.scoped_category and card.scoped_category != resolved_category:
        return TellerResult(
            AuthDecision.DECLINED, "category_mismatch", resolved_category
        )

    # Company spend policies — any deny wins.
    policies = (
        await session.execute(
            select(SpendPolicy).where(SpendPolicy.active.is_(True))
        )
    ).scalars().all()
    for policy in policies:
        denied = policy.denied_categories or []
        if resolved_category in denied:
            return TellerResult(
                AuthDecision.DECLINED, "policy_denied_category", resolved_category
            )
        if (
            policy.max_transaction_cents is not None
            and amount_cents > policy.max_transaction_cents
        ):
            return TellerResult(
                AuthDecision.DECLINED, "policy_over_max", resolved_category
            )

    if card.budget_id is not None:
        budget = (
            await session.execute(
                select(Budget)
                .where(Budget.id == card.budget_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if budget is None or not budget.active:
            return TellerResult(
                AuthDecision.DECLINED, "budget_inactive", resolved_category
            )
        month_start = date.today().replace(day=1)
        spent = (
            await session.execute(
                select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                    Transaction.budget_id == card.budget_id,
                    Transaction.occurred_on >= month_start,
                )
            )
        ).scalar_one()
        if int(spent) + amount_cents > budget.limit_cents:
            return TellerResult(
                AuthDecision.DECLINED, "budget_exceeded", resolved_category
            )

    per_diem = (
        await session.execute(
            select(PerDiem)
            .where(
                PerDiem.user_id == card.user_id,
                PerDiem.active.is_(True),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if per_diem is not None:
        today = date.today()
        spent_today = (
            await session.execute(
                select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                    Transaction.user_id == card.user_id,
                    Transaction.occurred_on == today,
                )
            )
        ).scalar_one()
        if int(spent_today) + amount_cents > per_diem.daily_limit_cents:
            return TellerResult(
                AuthDecision.DECLINED, "per_diem_exceeded", resolved_category
            )

    return TellerResult(AuthDecision.APPROVED, "ok", resolved_category)


async def load_issued_card(
    session: AsyncSession, card_id: uuid.UUID
) -> IssuedCard | None:
    return (
        await session.execute(select(IssuedCard).where(IssuedCard.id == card_id))
    ).scalar_one_or_none()
