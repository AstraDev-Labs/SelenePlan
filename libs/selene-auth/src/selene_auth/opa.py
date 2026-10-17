from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OPAResult(BaseModel):
    """Authorization evaluation result from Open Policy Agent."""

    allow: bool = Field(description="Authorization decision outcome")
    reason: str | None = Field(
        default=None, description="Explanation or denial reason if applicable"
    )
    raw_result: Any = Field(default=None, description="Underlying policy evaluation data")


class OPAClient:
    """Fail-closed Open Policy Agent (OPA) client."""

    def __init__(self, opa_url: str = "http://opa:8181", timeout_s: float = 2.0) -> None:
        self.opa_url = opa_url.rstrip("/")
        self.timeout_s = timeout_s

    async def evaluate(self, policy_path: str, input_data: dict[str, Any]) -> OPAResult:
        """Query OPA data API with structured input context.

        CRITICAL SECURITY INVARIANT: FAILS CLOSED.
        Any timeout, network error, non-200 status code, or undefined policy result
        evaluates strictly to allow=False.
        """
        clean_path = policy_path.strip("/").replace(".", "/")
        endpoint = f"{self.opa_url}/v1/data/{clean_path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                res = await client.post(endpoint, json={"input": input_data})

            if res.status_code != 200:
                logger.error(
                    "OPA error response %d from %s: %s", res.status_code, endpoint, res.text
                )
                return OPAResult(allow=False, reason=f"OPA returned HTTP {res.status_code}")

            data = res.json()
            # If the rule was undefined in OPA, the 'result' key will be None or omitted
            if "result" not in data or data["result"] is None:
                logger.warning("OPA rule '%s' produced an undefined result", policy_path)
                return OPAResult(allow=False, reason="Undefined policy result")

            raw_result = data["result"]

            if isinstance(raw_result, bool):
                return OPAResult(allow=raw_result, raw_result=raw_result)
            elif isinstance(raw_result, dict):
                # Standard pattern: {allow: true/false, reason: "..."}
                allow = bool(raw_result.get("allow", False))
                reason = raw_result.get("reason")
                return OPAResult(allow=allow, reason=reason, raw_result=raw_result)
            else:
                logger.warning(
                    "OPA rule '%s' returned unexpected result shape '%s' (failing closed)",
                    policy_path,
                    type(raw_result).__name__,
                )
                return OPAResult(
                    allow=False,
                    reason=f"Unexpected OPA result shape: {type(raw_result).__name__}",
                    raw_result=raw_result,
                )

        except httpx.TimeoutException as exc:
            logger.error("OPA evaluation timed out against %s: %s", endpoint, exc)
            return OPAResult(allow=False, reason="OPA timeout (fail-closed)")
        except Exception as exc:  # noqa: BLE001 - network or JSON parsing failure fails closed
            logger.error("OPA request failed against %s: %s", endpoint, exc)
            return OPAResult(allow=False, reason=f"OPA evaluation failed: {exc}")
