"""Shared FastAPI dependencies: role-based access control."""

from fastapi import HTTPException, Request

from backend.models import Role

MANAGERS = (Role.OWNER, Role.OFFICE_MANAGER)


def require_role(*allowed: Role):
    """Dependency factory: reject the request unless the caller's role
    (resolved from the database by the auth middleware) is in `allowed`."""

    allowed_values = {role.value for role in allowed}

    def checker(request: Request) -> str:
        role = getattr(request.state, "role", None)
        if role not in allowed_values:
            raise HTTPException(
                status_code=403,
                detail="Insufficient role for this operation",
            )
        return role

    return checker
