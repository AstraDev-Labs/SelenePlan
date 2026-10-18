from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from selene_auth.dependencies import (
    get_current_principal,
    require_mfa,
    require_roles,
    set_global_jwt_validator,
    verify_project_membership,
)
from selene_auth.jwt import JWTValidator
from selene_auth.principal import Principal


@pytest.fixture
def dummy_validator() -> MagicMock:
    validator = MagicMock(spec=JWTValidator)
    set_global_jwt_validator(validator)
    return validator


@pytest.mark.asyncio
async def test_get_current_principal_missing_header(dummy_validator: MagicMock) -> None:
    app = FastAPI()

    @app.get("/test")
    def endpoint(p: Principal = Depends(get_current_principal)) -> dict[str, str]:
        return {"sub": p.sub}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/test")
        assert res.status_code == 401
        data = res.json()
        assert data["detail"]["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_get_current_principal_invalid_format(dummy_validator: MagicMock) -> None:
    app = FastAPI()

    @app.get("/test")
    def endpoint(p: Principal = Depends(get_current_principal)) -> dict[str, str]:
        return {"sub": p.sub}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/test", headers={"Authorization": "Basic 12345"})
        assert res.status_code == 401
        data = res.json()
        assert data["detail"]["error"]["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_get_current_principal_valid_token(dummy_validator: MagicMock) -> None:
    expected_principal = Principal(sub="user-123", roles=["analyst"])
    dummy_validator.verify_token.return_value = expected_principal

    app = FastAPI()

    @app.get("/test")
    def endpoint(p: Principal = Depends(get_current_principal)) -> dict[str, str]:
        return {"sub": p.sub}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/test", headers={"Authorization": "Bearer valid.token.here"})
        assert res.status_code == 200
        assert res.json() == {"sub": "user-123"}


@pytest.mark.asyncio
async def test_require_roles_enforcement(dummy_validator: MagicMock) -> None:
    app = FastAPI()

    @app.get("/analyst-only")
    def analyst_endpoint(
        p: Principal = Depends(require_roles("analyst", "operator")),
    ) -> dict[str, str]:
        return {"status": "ok"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Matching role
        dummy_validator.verify_token.return_value = Principal(sub="u1", roles=["analyst"])
        res1 = await client.get("/analyst-only", headers={"Authorization": "Bearer t1"})
        assert res1.status_code == 200

        # 2. Admin role does NOT satisfy analyst/operator check -> 403 Forbidden
        dummy_validator.verify_token.return_value = Principal(sub="u2", roles=["admin"])
        res2 = await client.get("/analyst-only", headers={"Authorization": "Bearer t2"})
        assert res2.status_code == 403

        # 3. Missing role -> 403 Forbidden
        dummy_validator.verify_token.return_value = Principal(sub="u3", roles=["auditor"])
        res3 = await client.get("/analyst-only", headers={"Authorization": "Bearer t3"})
        assert res3.status_code == 403
        data = res3.json()
        assert data["detail"]["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_only_principal_gets_403_on_approver_only_endpoint(
    dummy_validator: MagicMock,
) -> None:
    app = FastAPI()

    @app.get("/approver-only")
    def approver_endpoint(
        p: Principal = Depends(require_roles("approver")),
    ) -> dict[str, str]:
        return {"status": "approved"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin does NOT satisfy approver role check
        dummy_validator.verify_token.return_value = Principal(sub="admin-user", roles=["admin"])
        res = await client.get("/approver-only", headers={"Authorization": "Bearer admin.token"})
        assert res.status_code == 403
        data = res.json()
        assert data["detail"]["error"]["code"] == "forbidden"
        assert "Requires one of roles" in data["detail"]["error"]["message"]


@pytest.mark.asyncio
async def test_require_mfa_enforcement(dummy_validator: MagicMock) -> None:
    app = FastAPI()

    @app.get("/sensitive")
    def sensitive_endpoint(p: Principal = Depends(require_mfa)) -> dict[str, str]:
        return {"status": "ok"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # MFA present
        dummy_validator.verify_token.return_value = Principal(sub="u1", mfa_verified=True)
        res1 = await client.get("/sensitive", headers={"Authorization": "Bearer t1"})
        assert res1.status_code == 200

        # MFA missing -> 403
        dummy_validator.verify_token.return_value = Principal(sub="u2", mfa_verified=False)
        res2 = await client.get("/sensitive", headers={"Authorization": "Bearer t2"})
        assert res2.status_code == 403
        assert res2.json()["detail"]["error"]["code"] == "mfa_required"


def test_verify_project_membership() -> None:
    member_principal = Principal(sub="user-1", roles=["analyst"])
    outsider_principal = Principal(sub="user-2", roles=["analyst"])
    admin_principal = Principal(sub="admin-user", roles=["admin"])

    project_members = ["user-1", "user-3"]

    assert verify_project_membership(member_principal, project_members) is True
    assert verify_project_membership(outsider_principal, project_members) is False
    assert verify_project_membership(admin_principal, project_members) is True


def test_get_global_jwt_validator_uninitialized() -> None:
    from selene_auth import dependencies
    from selene_auth.dependencies import get_global_jwt_validator

    saved = dependencies._GLOBAL_VALIDATOR
    try:
        dependencies._GLOBAL_VALIDATOR = None
        with pytest.raises(RuntimeError) as exc:
            get_global_jwt_validator()
        assert "not been initialized" in str(exc.value)
    finally:
        dependencies._GLOBAL_VALIDATOR = saved


@pytest.mark.asyncio
async def test_get_current_principal_auth_error(dummy_validator: MagicMock) -> None:
    from selene_auth.jwt import AuthError

    dummy_validator.verify_token.side_effect = AuthError("Token expired", code="token_expired")

    app = FastAPI()

    @app.get("/test")
    def endpoint(p: Principal = Depends(get_current_principal)) -> dict[str, str]:
        return {"sub": p.sub}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/test", headers={"Authorization": "Bearer bad.token"})
        assert res.status_code == 401
        data = res.json()
        assert data["detail"]["error"]["code"] == "token_expired"
