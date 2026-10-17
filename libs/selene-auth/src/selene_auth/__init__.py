"""SelenePlan Auth Library: Pinned JWT validation, Principal model, RBAC dependencies, and OPA client."""

from selene_auth.dependencies import (
    get_current_principal,
    get_global_jwt_validator,
    require_mfa,
    require_roles,
    set_global_jwt_validator,
    verify_project_membership,
)
from selene_auth.jwt import (
    ALLOWED_ALGORITHMS,
    AuthError,
    JWKSCache,
    JWTValidator,
)
from selene_auth.opa import OPAClient, OPAResult
from selene_auth.principal import Principal

__all__ = [
    "ALLOWED_ALGORITHMS",
    "AuthError",
    "JWKSCache",
    "JWTValidator",
    "OPAClient",
    "OPAResult",
    "Principal",
    "get_current_principal",
    "get_global_jwt_validator",
    "require_mfa",
    "require_roles",
    "set_global_jwt_validator",
    "verify_project_membership",
]
