"""Reward Router API: recommendations, decisions, and the rewards ledger.

Decisions are the audit-worthy events (captured by triggers); the ledger of
accepted decisions is the basis for Thesa's take-rate billing, so all figures
are recomputed server-side from transaction history — never taken from the
client.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import RoutingDecision, RoutingStatus
from backend.schemas import (
    RecommendationOut,
    RewardsLedgerOut,
    RoutingDecisionCreate,
    RoutingDecisionOut,
)
from backend.services.reward_router import (
    compute_recommendations,
    recommendation_for_vendor,
)

router = APIRouter(prefix="/routing", dependencies=[Depends(require_role(*MANAGERS))])


@router.get("/recommendations", response_model=list[RecommendationOut])
async def recommendations(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[RecommendationOut]:
    return [
        RecommendationOut(**rec.__dict__)
        for rec in await compute_recommendations(session)
    ]


@router.post("/decisions", response_model=RoutingDecisionOut, status_code=201)
async def record_decision(
    body: RoutingDecisionCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> RoutingDecisionOut:
    if body.status == RoutingStatus.RECOMMENDED:
        raise HTTPException(
            status_code=422,
            detail="Decision status must be 'accepted' or 'dismissed'",
        )

    rec = await recommendation_for_vendor(session, body.vendor_name)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail="No current recommendation for this vendor",
        )
    if rec.recommended_card_id != body.recommended_card_id:
        raise HTTPException(
            status_code=409,
            detail="Recommendation has changed; refresh and retry",
        )

    # The ledger sums accepted decisions (billing basis), so accepting the
    # same vendor twice would double-count uplift.
    existing = (
        await session.execute(
            select(RoutingDecision.id).where(
                func.lower(RoutingDecision.vendor_name) == rec.vendor_name.strip().lower(),
                RoutingDecision.status == RoutingStatus.ACCEPTED.value,
            )
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="An accepted routing decision already exists for this vendor",
        )

    decision = RoutingDecision(
        company_id=uuid.UUID(request.state.company_id),
        vendor_name=rec.vendor_name,
        category=rec.category.value,
        recommended_card_id=rec.recommended_card_id,
        previous_card_id=rec.current_card_id,
        status=body.status.value,
        est_monthly_spend_cents=rec.est_monthly_spend_cents,
        est_monthly_uplift_cents=rec.est_monthly_uplift_cents,
        decided_by=uuid.UUID(request.state.user_id),
    )
    session.add(decision)
    await session.flush()
    return RoutingDecisionOut.model_validate(decision, from_attributes=True)


@router.get("/decisions", response_model=list[RoutingDecisionOut])
async def list_decisions(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[RoutingDecisionOut]:
    decisions = (
        (
            await session.execute(
                select(RoutingDecision).order_by(RoutingDecision.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        RoutingDecisionOut.model_validate(d, from_attributes=True) for d in decisions
    ]


@router.get("/ledger", response_model=RewardsLedgerOut)
async def rewards_ledger(
    session: AsyncSession = Depends(get_tenant_session),
) -> RewardsLedgerOut:
    count, uplift = (
        await session.execute(
            select(
                func.count(RoutingDecision.id),
                func.coalesce(func.sum(RoutingDecision.est_monthly_uplift_cents), 0),
            ).where(RoutingDecision.status == RoutingStatus.ACCEPTED.value)
        )
    ).one()
    return RewardsLedgerOut(
        accepted_decisions=int(count),
        est_monthly_uplift_cents=int(uplift),
        est_annual_uplift_cents=int(uplift) * 12,
    )
