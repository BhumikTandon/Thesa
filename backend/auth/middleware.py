"""Authentication middleware: verifies Clerk session tokens and resolves the
user's Thesa identity from the database.

The Clerk SDK verifies the bearer token; the tenant (company_id) and role are
then looked up from the `users` table via the SECURITY DEFINER `resolve_user`
function — JWT public metadata is no longer trusted for tenancy, so membership
changes take effect immediately.

Users authenticated with Clerk but not yet linked to a company may only reach
the onboarding endpoint.
"""

from typing import Callable

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.config import get_settings
from backend.db.session import get_session_factory

_PUBLIC_PATHS: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"}

# Paths reachable by an authenticated Clerk user who has no company yet.
_ONBOARDING_PATHS: set[str] = {"/onboarding"}


def _to_httpx_request(request: Request) -> httpx.Request:
    """Convert a Starlette Request to an httpx.Request for the Clerk SDK."""
    return httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=dict(request.headers),
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Clerk-based session verification with database-backed tenancy.

    On success, request.state carries:
        clerk_user_id  Clerk subject (always set)
        user_id        Thesa user UUID (None until onboarded)
        company_id     tenant UUID (None until onboarded)
        role           owner | office_manager | crew_lead (None until onboarded)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        settings = get_settings()
        self._clerk = Clerk(bearer_auth=settings.clerk_secret_key)
        self._settings = settings

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )

        parts = auth_header.split(" ", maxsplit=1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization header format"},
            )

        httpx_request = _to_httpx_request(request)
        request_state = self._clerk.authenticate_request(
            httpx_request,
            AuthenticateRequestOptions(),
        )

        if not request_state.is_signed_in:
            reason = (
                str(request_state.reason)
                if request_state.reason
                else "Authentication failed"
            )
            return JSONResponse(status_code=401, content={"detail": reason})

        payload = request_state.payload or {}
        clerk_user_id = payload.get("sub")
        if not clerk_user_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has no subject claim"},
            )

        identity = await self._resolve_user(clerk_user_id)

        request.state.clerk_user_id = clerk_user_id

        if identity is None:
            if request.url.path in _ONBOARDING_PATHS:
                request.state.user_id = None
                request.state.company_id = None
                request.state.role = None
                return await call_next(request)
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "User is not a member of any company; "
                    "complete onboarding first"
                },
            )

        request.state.user_id = str(identity["user_id"])
        request.state.company_id = str(identity["company_id"])
        request.state.role = identity["role"]

        return await call_next(request)

    async def _resolve_user(self, clerk_user_id: str) -> dict | None:
        """Look up the Thesa user for a Clerk subject (parameterized)."""
        factory = get_session_factory(self._settings)
        async with factory() as session:
            result = await session.execute(
                text(
                    "SELECT user_id, company_id, role, email "
                    "FROM resolve_user(:clerk_user_id)"
                ),
                {"clerk_user_id": clerk_user_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None
