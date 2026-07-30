"""Team management: invites and member listing.

Managers invite by email + role; only the owner can invite another owner.
Invite creation, revocation, and acceptance are all captured by the
immutable audit triggers on `invites` and `users`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_tenant_session
from backend.deps import MANAGERS, require_role
from backend.models import Invite, InviteStatus, Role, User
from backend.schemas import InviteCreate, InviteOut, MemberOut

router = APIRouter(prefix="/team")


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[MemberOut]:
    users = (
        (await session.execute(select(User).order_by(User.created_at)))
        .scalars()
        .all()
    )
    return [MemberOut.model_validate(u, from_attributes=True) for u in users]


@router.get(
    "/invites",
    response_model=list[InviteOut],
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def list_invites(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[InviteOut]:
    invites = (
        (await session.execute(select(Invite).order_by(Invite.created_at.desc())))
        .scalars()
        .all()
    )
    return [InviteOut.model_validate(i, from_attributes=True) for i in invites]


@router.post(
    "/invites",
    response_model=InviteOut,
    status_code=201,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def create_invite(
    body: InviteCreate,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> InviteOut:
    if body.role == Role.OWNER and request.state.role != Role.OWNER.value:
        raise HTTPException(
            status_code=403, detail="Only the owner can invite another owner"
        )

    existing_member = (
        await session.execute(select(User.id).where(User.email == body.email))
    ).first()
    if existing_member is not None:
        raise HTTPException(
            status_code=409, detail="A member with this email already exists"
        )

    invite = Invite(
        company_id=uuid.UUID(request.state.company_id),
        email=body.email,
        role=body.role.value,
        invited_by=uuid.UUID(request.state.user_id),
    )
    session.add(invite)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="A pending invite for this email already exists"
        ) from None
    return InviteOut.model_validate(invite, from_attributes=True)


@router.post(
    "/invites/{invite_id}/revoke",
    response_model=InviteOut,
    dependencies=[Depends(require_role(*MANAGERS))],
)
async def revoke_invite(
    invite_id: uuid.UUID,
    session: AsyncSession = Depends(get_tenant_session),
) -> InviteOut:
    invite = (
        await session.execute(select(Invite).where(Invite.id == invite_id))
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != InviteStatus.PENDING.value:
        raise HTTPException(
            status_code=409, detail=f"Invite is already {invite.status}"
        )

    invite.status = InviteStatus.REVOKED.value
    await session.flush()
    return InviteOut.model_validate(invite, from_attributes=True)
