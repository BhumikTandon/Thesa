"""Per diems: daily allowances for field employees.

Managers set them; any employee can check their own remaining balance for
today (the primary field-client view).
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import PerDiem, Transaction, User
from backend.schemas import PerDiemCreate, PerDiemOut, PerDiemStatus

router = APIRouter(prefix="/per-diems")


def _to_out(per_diem: PerDiem) -> PerDiemOut:
    return PerDiemOut(
        id=per_diem.id,
        user_id=per_diem.user_id,
        daily_limit_cents=per_diem.daily_limit_cents,
        active=per_diem.active,
        created_at=per_diem.created_at,
    )


@router.get(
    "",
    response_model=list[PerDiemOut],
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def list_per_diems(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[PerDiemOut]:
    per_diems = (await session.execute(select(PerDiem))).scalars().all()
    return [_to_out(p) for p in per_diems]


@router.post(
    "",
    response_model=PerDiemOut,
    status_code=201,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def create_per_diem(
    body: PerDiemCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> PerDiemOut:
    # RLS guarantees this lookup only sees the tenant's own users, so a
    # cross-tenant user_id comes back as "not found".
    user = (
        await session.execute(select(User).where(User.id == body.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    per_diem = PerDiem(
        company_id=uuid.UUID(request.state.company_id),
        user_id=body.user_id,
        daily_limit_cents=body.daily_limit_cents,
    )
    session.add(per_diem)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="User already has a per diem"
        ) from None
    return _to_out(per_diem)


@router.get("/me", response_model=PerDiemStatus)
async def my_per_diem_status(
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> PerDiemStatus:
    user_id = uuid.UUID(request.state.user_id)

    per_diem = (
        await session.execute(
            select(PerDiem).where(PerDiem.user_id == user_id, PerDiem.active)
        )
    ).scalar_one_or_none()
    if per_diem is None:
        raise HTTPException(status_code=404, detail="No active per diem")

    spent_today = (
        await session.execute(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                Transaction.user_id == user_id,
                Transaction.occurred_on == date.today(),
            )
        )
    ).scalar_one()

    return PerDiemStatus(
        daily_limit_cents=per_diem.daily_limit_cents,
        spent_today_cents=int(spent_today),
        remaining_today_cents=max(0, per_diem.daily_limit_cents - int(spent_today)),
    )
