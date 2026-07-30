"""Company spend policies — Card Teller deny rules."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import SpendCategory, SpendPolicy
from backend.schemas import SpendPolicyCreate, SpendPolicyOut, SpendPolicyUpdate

router = APIRouter(prefix="/spend-policies")


def _to_out(policy: SpendPolicy) -> SpendPolicyOut:
    cats = [
        SpendCategory(c)
        for c in (policy.denied_categories or [])
        if c in SpendCategory._value2member_map_
    ]
    return SpendPolicyOut(
        id=policy.id,
        name=policy.name,
        denied_categories=cats,
        max_transaction_cents=policy.max_transaction_cents,
        active=policy.active,
        created_at=policy.created_at,
    )


@router.get("", response_model=list[SpendPolicyOut])
async def list_policies(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[SpendPolicyOut]:
    rows = (await session.execute(select(SpendPolicy))).scalars().all()
    return [_to_out(p) for p in rows]


@router.post(
    "",
    response_model=SpendPolicyOut,
    status_code=201,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def create_policy(
    body: SpendPolicyCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> SpendPolicyOut:
    policy = SpendPolicy(
        company_id=uuid.UUID(request.state.company_id),
        name=body.name,
        denied_categories=[c.value for c in body.denied_categories],
        max_transaction_cents=body.max_transaction_cents,
    )
    session.add(policy)
    await session.flush()
    return _to_out(policy)


@router.patch(
    "/{policy_id}",
    response_model=SpendPolicyOut,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def update_policy(
    policy_id: uuid.UUID,
    body: SpendPolicyUpdate,
    session: AsyncSession = Depends(get_tenant_session),
) -> SpendPolicyOut:
    policy = (
        await session.execute(select(SpendPolicy).where(SpendPolicy.id == policy_id))
    ).scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    if body.denied_categories is not None:
        policy.denied_categories = [c.value for c in body.denied_categories]
    if body.max_transaction_cents is not None:
        policy.max_transaction_cents = body.max_transaction_cents
    if body.active is not None:
        policy.active = body.active
    await session.flush()
    return _to_out(policy)
