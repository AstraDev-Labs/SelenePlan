from __future__ import annotations

import httpx
import pytest
from selene_auth.opa import OPAClient


@pytest.mark.asyncio
async def test_opa_client_allow_true_boolean() -> None:
    from unittest.mock import MagicMock, patch

    client = OPAClient(opa_url="http://mock-opa:8181")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": True}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("example.allow", {"role": "admin"})
        assert res.allow is True
        assert res.raw_result is True


@pytest.mark.asyncio
async def test_opa_client_evaluation_logic() -> None:
    # Test allow true with dict
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"allow": True}}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("selene.project.access", {"user": "analyst"})
        assert res.allow is True
        assert res.raw_result == {"allow": True}


@pytest.mark.asyncio
async def test_opa_client_fails_closed_on_undefined_result() -> None:
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # OPA returns empty object or null result when rule is undefined
    mock_resp.json.return_value = {"result": None}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("selene.unknown.rule", {"user": "analyst"})
        assert res.allow is False
        assert "Undefined policy result" in str(res.reason)


@pytest.mark.asyncio
async def test_opa_client_fails_closed_on_http_error() -> None:
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import AsyncMock, patch

    mock_resp = AsyncMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("selene.project.access", {"user": "analyst"})
        assert res.allow is False
        assert "HTTP 500" in str(res.reason)


@pytest.mark.asyncio
async def test_opa_client_fails_closed_on_timeout() -> None:
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import patch

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        res = await client.evaluate("selene.project.access", {"user": "analyst"})
        assert res.allow is False
        assert "timeout" in str(res.reason).lower()


@pytest.mark.asyncio
async def test_opa_client_fails_closed_on_malformed_json() -> None:
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON response from server")

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("selene.project.access", {"user": "analyst"})
        assert res.allow is False
        assert "evaluation failed" in str(res.reason).lower()


@pytest.mark.asyncio
async def test_opa_client_fails_closed_on_unexpected_result_shape() -> None:
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": ["list", "of", "items"]}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("selene.project.access", {"user": "analyst"})
        assert res.allow is False
        assert "unexpected opa result shape" in str(res.reason).lower()


@pytest.mark.asyncio
async def test_opa_client_denial_dict() -> None:
    client = OPAClient(opa_url="http://mock-opa:8181")

    from unittest.mock import MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"allow": False, "reason": "Insufficient clearance"}}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.evaluate("selene.project.access", {"user": "analyst"})
        assert res.allow is False
        assert res.reason == "Insufficient clearance"
