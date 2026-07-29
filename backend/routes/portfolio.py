"""Card portfolio: the company's existing corporate cards and their earn
rates. Input to the Reward Router. All changes are captured by audit triggers.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import PortfolioCard, RewardRule
from backend.schemas import (
    PortfolioCardCreate,
    PortfolioCardOut,
    PortfolioCardUpdate,
    RewardRuleOut,
)

router = APIRouter(prefix="/portfolio-cards")


def _to_out(card: PortfolioCard, rules: list[RewardRule]) -> PortfolioCardOut:
    return PortfolioCardOut(
        id=card.id,
        label=card.label,
        issuer=card.issuer,
        last4=card.last4,
        default_reward_pct=card.default_reward_pct,
        active=card.active,
        rules=[
            RewardRuleOut(id=r.id, category=r.category, reward_pct=r.reward_pct)
            for r in rules
        ],
        created_at=card.created_at,
    )


@router.get("", response_model=list[PortfolioCardOut])
async def list_cards(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[PortfolioCardOut]:
    cards = (await session.execute(select(PortfolioCard))).scalars().all()
    rules = (await session.execute(select(RewardRule))).scalars().all()
    by_card: dict[uuid.UUID, list[RewardRule]] = {}
    for rule in rules:
        by_card.setdefault(rule.portfolio_card_id, []).append(rule)
    return [_to_out(card, by_card.get(card.id, [])) for card in cards]


@router.post(
    "",
    response_model=PortfolioCardOut,
    status_code=201,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def create_card(
    body: PortfolioCardCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> PortfolioCardOut:
    company_id = uuid.UUID(request.state.company_id)

    seen = {rule.category for rule in body.rules}
    if len(seen) != len(body.rules):
        raise HTTPException(status_code=422, detail="Duplicate rule categories")

    card = PortfolioCard(
        company_id=company_id,
        label=body.label,
        issuer=body.issuer,
        last4=body.last4,
        default_reward_pct=body.default_reward_pct,
    )
    session.add(card)
    await session.flush()

    rules = [
        RewardRule(
            company_id=company_id,
            portfolio_card_id=card.id,
            category=rule.category.value,
            reward_pct=rule.reward_pct,
        )
        for rule in body.rules
    ]
    session.add_all(rules)
    await session.flush()

    return _to_out(card, rules)


@router.patch(
    "/{card_id}",
    response_model=PortfolioCardOut,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def update_card(
    card_id: uuid.UUID,
    body: PortfolioCardUpdate,
    session: AsyncSession = Depends(get_tenant_session),
) -> PortfolioCardOut:
    card = (
        await session.execute(
            select(PortfolioCard).where(PortfolioCard.id == card_id)
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    card.active = body.active
    await session.flush()

    rules = (
        (
            await session.execute(
                select(RewardRule).where(RewardRule.portfolio_card_id == card.id)
            )
        )
        .scalars()
        .all()
    )
    return _to_out(card, list(rules))
