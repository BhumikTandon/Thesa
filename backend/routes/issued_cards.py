"""Thesa-issued virtual cards (stub issuer today; Marqeta later)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import (
    Budget,
    IssuedCard,
    IssuedCardStatus,
    Role,
    SpendCategory,
    User,
)
from backend.schemas import IssuedCardCreate, IssuedCardOut, IssuedCardUpdate
from backend.services import issuing_stub

router = APIRouter(prefix="/issued-cards")


def _to_out(card: IssuedCard) -> IssuedCardOut:
    return IssuedCardOut(
        id=card.id,
        user_id=card.user_id,
        budget_id=card.budget_id,
        label=card.label,
        last4=card.last4,
        status=IssuedCardStatus(card.status),
        scoped_vendor=card.scoped_vendor,
        scoped_category=(
            SpendCategory(card.scoped_category) if card.scoped_category else None
        ),
        single_tx_limit_cents=card.single_tx_limit_cents,
        expires_at=card.expires_at,
        created_at=card.created_at,
    )


@router.get("", response_model=list[IssuedCardOut])
async def list_cards(
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> list[IssuedCardOut]:
    """Managers see all company cards; crew leads see only their own."""
    query = select(IssuedCard)
    if request.state.role == Role.CREW_LEAD.value:
        query = query.where(IssuedCard.user_id == uuid.UUID(request.state.user_id))
    rows = (await session.execute(query)).scalars().all()
    return [_to_out(c) for c in rows]


@router.post("", response_model=IssuedCardOut, status_code=201)
async def provision_card(
    body: IssuedCardCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> IssuedCardOut:
    """Provision a scoped virtual card via the stub issuer.

    Crew leads may only issue to themselves. Managers may issue to any
    company member.
    """
    company_id = uuid.UUID(request.state.company_id)
    caller_id = uuid.UUID(request.state.user_id)
    target_user_id = body.user_id or caller_id

    if (
        request.state.role == Role.CREW_LEAD.value
        and target_user_id != caller_id
    ):
        raise HTTPException(
            status_code=403, detail="Crew leads may only issue cards to themselves"
        )

    target = (
        await session.execute(select(User).where(User.id == target_user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.budget_id is not None:
        budget = (
            await session.execute(select(Budget).where(Budget.id == body.budget_id))
        ).scalar_one_or_none()
        if budget is None or not budget.active:
            raise HTTPException(status_code=400, detail="Budget not found or inactive")

    provisioned = issuing_stub.provision_card(
        label=body.label, company_id=company_id
    )
    card = IssuedCard(
        company_id=company_id,
        user_id=target_user_id,
        budget_id=body.budget_id,
        label=body.label,
        external_token=provisioned.external_token,
        last4=provisioned.last4,
        status=IssuedCardStatus.ACTIVE.value,
        scoped_vendor=body.scoped_vendor,
        scoped_category=(
            body.scoped_category.value if body.scoped_category else None
        ),
        single_tx_limit_cents=body.single_tx_limit_cents,
        expires_at=body.expires_at,
    )
    session.add(card)
    await session.flush()
    return _to_out(card)


@router.patch(
    "/{card_id}",
    response_model=IssuedCardOut,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def update_card(
    card_id: uuid.UUID,
    body: IssuedCardUpdate,
    session: AsyncSession = Depends(get_tenant_session),
) -> IssuedCardOut:
    card = (
        await session.execute(select(IssuedCard).where(IssuedCard.id == card_id))
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    if body.status == IssuedCardStatus.REQUESTED:
        raise HTTPException(status_code=400, detail="Cannot set status to requested")
    if (
        card.status == IssuedCardStatus.CANCELED.value
        and body.status != IssuedCardStatus.CANCELED
    ):
        raise HTTPException(
            status_code=400, detail="Canceled cards cannot be reactivated"
        )

    if body.status == IssuedCardStatus.FROZEN:
        issuing_stub.freeze_card(card.external_token)
    elif body.status == IssuedCardStatus.CANCELED:
        issuing_stub.cancel_card(card.external_token)

    card.status = body.status.value
    await session.flush()
    return _to_out(card)
