"""Onboarding: create a company and its owner for a new Clerk user.

The only endpoint reachable by an authenticated user with no company. Goes
through the SECURITY DEFINER `create_company_with_owner` function because no
tenant context exists yet (RLS fails closed on plain sessions).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_plain_session
from backend.models import Role
from backend.schemas import OnboardingRequest, OnboardingResponse

router = APIRouter()


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
