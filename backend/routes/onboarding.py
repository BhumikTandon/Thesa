"""Onboarding: create a company (owner path) or join one via invite.

The only endpoints reachable by an authenticated user with no company. Both
go through SECURITY DEFINER functions because no tenant context exists yet
(RLS fails closed on plain sessions).
"""

from clerk_backend_api import Clerk
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.config import get_settings
from backend.db.session import get_plain_session
from backend.models import Role
from backend.schemas import OnboardingRequest, OnboardingResponse

router = APIRouter()


def _get_clerk_email(clerk_user_id: str) -> str | None:
    """Fetch the caller's primary verified email from Clerk (server-side).

    The join flow must never trust a client-supplied email — an attacker
    could otherwise claim any pending invite.
    """
    clerk = Clerk(bearer_auth=get_settings().clerk_secret_key)
    user = clerk.users.get(user_id=clerk_user_id)
    if user is None or not user.email_addresses:
        return None
    for address in user.email_addresses:
        if address.id == user.primary_email_address_id:
            return address.email_address
    return user.email_addresses[0].email_address


@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
async def onboard(
    body: OnboardingRequest,
    request: Request,
    session: AsyncSession = Depends(get_plain_session),
) -> OnboardingResponse:
    if request.state.company_id is not None:
        raise HTTPException(
            status_code=409, detail="User already belongs to a company"
        )

    try:
        result = await session.execute(
            text(
                "SELECT company_id, user_id FROM create_company_with_owner("
                ":company_name, :clerk_user_id, :email)"
            ),
            {
                "company_name": body.company_name,
                "clerk_user_id": request.state.clerk_user_id,
                "email": body.email,
            },
        )
    except DBAPIError as exc:
        # unique_violation raised by the function when the Clerk user is
        # already linked (e.g. concurrent double-submit).
        if "unique" in str(exc.orig).lower():
            raise HTTPException(
                status_code=409, detail="User already belongs to a company"
            ) from exc
        raise

    row = result.one()
    return OnboardingResponse(
        company_id=row.company_id, user_id=row.user_id, role=Role.OWNER
    )


@router.post("/join", response_model=OnboardingResponse, status_code=201)
async def join(
    request: Request,
    session: AsyncSession = Depends(get_plain_session),
) -> OnboardingResponse:
    """Join a company via a pending invite matching the caller's Clerk email."""
    if request.state.company_id is not None:
        raise HTTPException(
            status_code=409, detail="User already belongs to a company"
        )

    email = await run_in_threadpool(_get_clerk_email, request.state.clerk_user_id)
    if not email:
        raise HTTPException(
            status_code=422, detail="No verified email on the Clerk account"
        )

    try:
        result = await session.execute(
            text(
                "SELECT company_id, user_id, role FROM accept_invite("
                ":clerk_user_id, :email)"
            ),
            {"clerk_user_id": request.state.clerk_user_id, "email": email},
        )
        row = result.one()
    except DBAPIError as exc:
        message = str(exc.orig).lower()
        if "no pending invite" in message:
            raise HTTPException(
                status_code=404, detail="No pending invite for this email"
            ) from exc
        if "already belongs" in message or "unique" in message:
            raise HTTPException(
                status_code=409, detail="User already belongs to a company"
            ) from exc
        raise

    return OnboardingResponse(
        company_id=row.company_id, user_id=row.user_id, role=Role(row.role)
    )
