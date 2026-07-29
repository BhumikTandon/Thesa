"""Reward Router: route recurring vendor spend to the highest-earning card.

The flagship engine. For each vendor seen in the lookback window it compares
the percent-back earned on the card(s) currently used against the best card
in the company's portfolio for that vendor's category, and quantifies the
monthly uplift of switching. All figures are integer cents; percentages are
exact decimals.

Uplift figures are always recomputed server-side from transaction history —
client-supplied numbers are never trusted (zero-trust rule).
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PortfolioCard, RewardRule, SpendCategory, Transaction

LOOKBACK_DAYS = 90
_LOOKBACK_MONTHS = Decimal(LOOKBACK_DAYS) / Decimal(30)


@dataclass(frozen=True)
class CardEarnRates:
    card_id: uuid.UUID
    label: str
    default_pct: Decimal
    category_pct: dict[str, Decimal]

    def pct_for(self, category: str) -> Decimal:
        return self.category_pct.get(category, self.default_pct)


@dataclass(frozen=True)
class Recommendation:
    vendor_name: str
    category: SpendCategory
    est_monthly_spend_cents: int
    current_card_id: uuid.UUID | None
    current_reward_pct: Decimal
    recommended_card_id: uuid.UUID
    recommended_card_label: str
    recommended_reward_pct: Decimal
    est_monthly_uplift_cents: int


async def load_earn_rates(session: AsyncSession) -> list[CardEarnRates]:
    """Load active portfolio cards with their category earn rates (RLS-scoped)."""
    cards = (
        (await session.execute(select(PortfolioCard).where(PortfolioCard.active)))
        .scalars()
        .all()
    )
    rules = (await session.execute(select(RewardRule))).scalars().all()

    rules_by_card: dict[uuid.UUID, dict[str, Decimal]] = {}
    for rule in rules:
        rules_by_card.setdefault(rule.portfolio_card_id, {})[rule.category] = (
            rule.reward_pct
        )

    return [
        CardEarnRates(
            card_id=card.id,
            label=card.label,
            default_pct=card.default_reward_pct,
            category_pct=rules_by_card.get(card.id, {}),
        )
        for card in cards
    ]


def best_card_for(
    cards: list[CardEarnRates], category: str
) -> tuple[CardEarnRates, Decimal] | None:
    if not cards:
        return None
    best = max(cards, key=lambda c: c.pct_for(category))
    return best, best.pct_for(category)


@dataclass(frozen=True)
class VendorSpend:
    vendor_name: str
    category: str
    total_cents: int
    dominant_card_id: uuid.UUID | None


async def aggregate_vendor_spend(session: AsyncSession) -> list[VendorSpend]:
    """Group lookback-window transactions by vendor (RLS scopes to tenant)."""
    since = date.today() - timedelta(days=LOOKBACK_DAYS)

    vendor_rows = (
        await session.execute(
            select(
                func.lower(Transaction.merchant_name).label("vendor"),
                func.max(Transaction.merchant_name).label("display_name"),
                func.max(Transaction.category).label("category"),
                func.sum(Transaction.amount_cents).label("total_cents"),
            )
            .where(Transaction.occurred_on >= since)
            .group_by(func.lower(Transaction.merchant_name))
        )
    ).all()

    # Dominant card per vendor: the portfolio card with the most spend.
    card_rows = (
        await session.execute(
            select(
                func.lower(Transaction.merchant_name).label("vendor"),
                Transaction.portfolio_card_id,
                func.sum(Transaction.amount_cents).label("card_cents"),
            )
            .where(Transaction.occurred_on >= since)
            .group_by(
                func.lower(Transaction.merchant_name),
                Transaction.portfolio_card_id,
            )
        )
    ).all()

    top_card: dict[str, tuple[uuid.UUID | None, int]] = {}
    for row in card_rows:
        current = top_card.get(row.vendor)
        if current is None or row.card_cents > current[1]:
            top_card[row.vendor] = (row.portfolio_card_id, row.card_cents)

    return [
        VendorSpend(
            vendor_name=row.display_name,
            category=row.category,
            total_cents=int(row.total_cents),
            dominant_card_id=top_card.get(row.vendor, (None, 0))[0],
        )
        for row in vendor_rows
    ]


async def compute_recommendations(session: AsyncSession) -> list[Recommendation]:
    """Produce positive-uplift routing recommendations for the tenant."""
    cards = await load_earn_rates(session)
    if not cards:
        return []
    rates_by_id = {c.card_id: c for c in cards}

    recommendations: list[Recommendation] = []
    for vendor in await aggregate_vendor_spend(session):
        best = best_card_for(cards, vendor.category)
        if best is None:
            continue
        best_card, best_pct = best

        current_card = (
            rates_by_id.get(vendor.dominant_card_id)
            if vendor.dominant_card_id
            else None
        )
        # Spend not on any registered card earns nothing today.
        current_pct = (
            current_card.pct_for(vendor.category)
            if current_card
            else Decimal("0.00")
        )

        monthly_spend = int(Decimal(vendor.total_cents) / _LOOKBACK_MONTHS)
        uplift = int(monthly_spend * (best_pct - current_pct) / Decimal(100))
        if uplift <= 0:
            continue

        recommendations.append(
            Recommendation(
                vendor_name=vendor.vendor_name,
                category=SpendCategory(vendor.category),
                est_monthly_spend_cents=monthly_spend,
                current_card_id=vendor.dominant_card_id,
                current_reward_pct=current_pct,
                recommended_card_id=best_card.card_id,
                recommended_card_label=best_card.label,
                recommended_reward_pct=best_pct,
                est_monthly_uplift_cents=uplift,
            )
        )

    recommendations.sort(key=lambda r: r.est_monthly_uplift_cents, reverse=True)
    return recommendations


async def recommendation_for_vendor(
    session: AsyncSession, vendor_name: str
) -> Recommendation | None:
    """Recompute the recommendation for one vendor (used when recording a
    decision, so ledger figures come from our data, not the client)."""
    normalized = vendor_name.strip().lower()
    for rec in await compute_recommendations(session):
        if rec.vendor_name.strip().lower() == normalized:
            return rec
    return None
