"""Authentication middleware: verifies Clerk session tokens and extracts company_id.

Uses Clerk's backend SDK to verify the bearer token against our Clerk instance.
On success, request.state.company_id is set from the session's public metadata.
"""

import uuid
from typing import Callable

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.config import get_settings

_PUBLIC_PATHS: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"}


def _to_httpx_request(request: Request) -> httpx.Request:
    """Convert a Starlette Request to an httpx.Request for the Clerk SDK."""
    return httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=dict(request.headers),
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Clerk-based session verification middleware.

    Rejects any request (outside _PUBLIC_PATHS) that does not carry a valid
    Clerk session token with a company_id in the user's public metadata.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        settings = get_settings()
        self._clerk = Clerk(bearer_auth=settings.clerk_secret_key)

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
            reason = str(request_state.reason) if request_state.reason else "Authentication failed"
            return JSONResponse(
                status_code=401,
                content={"detail": reason},
            )

        payload = request_state.payload or {}
        public_metadata = payload.get("public_metadata", {})
        company_id = public_metadata.get("company_id")

        if not company_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "No company_id in session public metadata"},
            )

        try:
            company_uuid = uuid.UUID(company_id)
        except (ValueError, AttributeError):
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid company_id format in metadata"},
            )

        request.state.company_id = str(company_uuid)
        request.state.user_id = payload.get("sub")

        return await call_next(request)
