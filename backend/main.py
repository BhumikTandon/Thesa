import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.auth.middleware import AuthMiddleware
from backend.config import get_settings
from backend.routes import (
    authorization_decisions,
    budgets,
    issued_cards,
    onboarding,
    per_diems,
    portfolio,
    routing,
    spend_policies,
    team,
    transactions,
    webhooks,
)
from backend.schemas import MeResponse
from backend.security import RateLimitMiddleware, SecurityHeadersMiddleware

app = FastAPI(title="Thesa", docs_url="/docs")

# Starlette middleware is LIFO: last added runs first. Execution order is
# SecurityHeaders -> Auth -> RateLimit -> routes, so headers are stamped on
# every response (including 401/429) and rate limiting can key on the
# identity that auth resolved.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
# CORS is outermost so preflight OPTIONS requests (which carry no bearer
# token) are answered before the auth middleware can reject them. Explicit
# origin allowlist, no credentials (bearer-token auth only).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Thesa-Signature", "X-Thesa-Timestamp"],
    allow_credentials=False,
    max_age=600,
)

app.include_router(onboarding.router)
app.include_router(team.router)
app.include_router(portfolio.router)
app.include_router(budgets.router)
app.include_router(per_diems.router)
app.include_router(transactions.router)
app.include_router(routing.router)
app.include_router(spend_policies.router)
app.include_router(issued_cards.router)
app.include_router(authorization_decisions.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/me", response_model=MeResponse)
async def me(request: Request) -> MeResponse:
    """The caller's identity as resolved from the database by auth middleware."""
    return MeResponse(
        user_id=uuid.UUID(request.state.user_id),
        company_id=uuid.UUID(request.state.company_id),
        clerk_user_id=request.state.clerk_user_id,
        role=request.state.role,
    )
