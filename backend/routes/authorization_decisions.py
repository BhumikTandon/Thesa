"""Authorization decision history (Card Teller outcomes)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import AuthDecision, AuthorizationDecision, SpendCategory
from backend.schemas import AuthorizationDecisionOut

router = APIRouter(prefix="/authorization-decisions")


@router.get(
    "",
    response_model=list[AuthorizationDecisionOut],
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def list_decisions(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[AuthorizationDecisionOut]:
    rows = (
        await session.execute(
            select(AuthorizationDecision).order_by(
                AuthorizationDecision.created_at.desc()
            )
        )
    ).scalars().all()
    return [
        AuthorizationDecisionOut(
            id=r.id,
            issued_card_id=r.issued_card_id,
            event_id=r.event_id,
            merchant_name=r.merchant_name,
            category=SpendCategory(r.category),
            amount_cents=r.amount_cents,
            decision=AuthDecision(r.decision),
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]
