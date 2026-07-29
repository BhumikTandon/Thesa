import uuid

from fastapi import FastAPI, Request

from backend.auth.middleware import AuthMiddleware
from backend.routes import budgets, onboarding, per_diems, portfolio, routing, transactions
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

app.include_router(onboarding.router)
app.include_router(portfolio.router)
app.include_router(budgets.router)
app.include_router(per_diems.router)
app.include_router(transactions.router)
app.include_router(routing.router)


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
