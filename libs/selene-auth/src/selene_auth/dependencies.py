from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

from selene_auth.jwt import AuthError, JWTValidator
from selene_auth.principal import Principal

_GLOBAL_VALIDATOR: JWTValidator | None = None


def set_global_jwt_validator(validator: JWTValidator) -> None:
    """Register the service-wide JWT validator instance."""
    global _GLOBAL_VALIDATOR
    _GLOBAL_VALIDATOR = validator


def get_global_jwt_validator() -> JWTValidator:
    """Retrieve the registered JWT validator."""
    if _GLOBAL_VALIDATOR is None:
        raise RuntimeError(
            "JWTValidator has not been initialized. Call set_global_jwt_validator() first."
        )
    return _GLOBAL_VALIDATOR


def get_current_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    validator: JWTValidator = Depends(get_global_jwt_validator),
) -> Principal:
    """FastAPI dependency extracting and validating Bearer JWT into Principal."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Missing Authorization header"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Authorization header must be Bearer <token>",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    try:
        principal = validator.verify_token(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": exc.code, "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return principal


def require_roles(*allowed_roles: str) -> Callable[[Principal], Principal]:
    """Dependency factory checking that the authenticated principal holds at least one allowed role."""

    def role_checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not any(role in principal.roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "forbidden",
                        "message": f"Requires one of roles: {list(allowed_roles)}",
                        "details": [{"user_roles": principal.roles}],
                    }
                },
            )
        return principal

    return role_checker


def require_mfa(principal: Principal = Depends(get_current_principal)) -> Principal:
    """FastAPI dependency ensuring the principal authenticated with multi-factor authentication."""
    if not principal.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "mfa_required",
                    "message": "Action requires multi-factor authentication (MFA)",
                }
            },
        )
    return principal


def verify_project_membership(
    principal: Principal,
    project_members: list[str],
) -> bool:
    """Verify if principal is an authorized member of a project or an admin."""
    if "admin" in principal.roles:
        return True
    return principal.sub in project_members
