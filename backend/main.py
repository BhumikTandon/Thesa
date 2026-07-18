from fastapi import Depends, FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.middleware import AuthMiddleware
from backend.db.session import get_tenant_session

app = FastAPI(title="Thesa", docs_url="/docs")
app.add_middleware(AuthMiddleware)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/me")
async def me(
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict:
    """Example authenticated endpoint demonstrating tenant-scoped session."""
    return {
        "company_id": request.state.company_id,
        "user_id": request.state.user_id,
    }
