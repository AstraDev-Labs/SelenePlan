from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Principal(BaseModel):
    """Authenticated user or service principal parsed from verified JWT."""

    sub: str = Field(description="Subject identifier (user UUID or service client ID)")
    roles: list[str] = Field(default_factory=list, description="Assigned realm roles")
    org_id: str | None = Field(default=None, description="Organization ID if bound to tenant")
    mfa_verified: bool = Field(
        default=False, description="True if MFA authentication was confirmed"
    )
    email: str | None = Field(default=None, description="Principal email address")
    claims: dict[str, Any] = Field(default_factory=dict, description="Raw verified JWT claims")

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> Principal:
        """Construct a Principal instance from verified claims."""
        sub = str(claims.get("sub", ""))
        org_id = claims.get("org_id")
        email = claims.get("email")

        # Extract realm roles from standard Keycloak format or direct roles claim
        roles: list[str] = []
        if "roles" in claims and isinstance(claims["roles"], list):
            roles.extend([str(r) for r in claims["roles"]])
        realm_access = claims.get("realm_access")
        if isinstance(realm_access, dict):
            realm_roles = realm_access.get("roles")
            if isinstance(realm_roles, list):
                for r in realm_roles:
                    r_str = str(r)
                    if r_str not in roles:
                        roles.append(r_str)

        # Compute mfa_verified from amr (Authentication Methods References) or acr
        mfa_verified = False
        amr = claims.get("amr")
        mfa_indicators = {"mfa", "otp", "totp", "webauthn", "fido", "hwk", "sms"}

        if isinstance(amr, list):
            if any(str(method).lower() in mfa_indicators for method in amr):
                mfa_verified = True
        elif isinstance(amr, str) and amr.lower() in mfa_indicators:
            mfa_verified = True

        acr = claims.get("acr")
        if acr in {"mfa", "level2", "gold", "2", 2}:
            mfa_verified = True

        return cls(
            sub=sub,
            roles=roles,
            org_id=str(org_id) if org_id is not None else None,
            mfa_verified=mfa_verified,
            email=str(email) if email is not None else None,
            claims=claims,
        )
