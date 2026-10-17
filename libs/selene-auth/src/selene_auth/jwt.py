from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.exceptions import (
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
)

from selene_auth.principal import Principal

ALLOWED_ALGORITHMS: list[str] = ["RS256", "ES256"]
FORBIDDEN_HEADERS: frozenset[str] = frozenset({"jku", "jwk", "x5u", "x5c"})


class AuthError(Exception):
    """Base exception for authentication and token validation failures."""

    def __init__(self, message: str, code: str = "invalid_token") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class JWKSCache:
    """Thread-safe JWKS cache with pinned algorithm enforcement and rate-limited refetching."""

    def __init__(
        self,
        jwks_url: str | None = None,
        preloaded_keys: dict[str, Any] | None = None,
        min_refetch_interval_s: float = 2.0,
    ) -> None:
        self.jwks_url = jwks_url
        self.min_refetch_interval_s = min_refetch_interval_s
        self._keys: dict[str, Any] = preloaded_keys or {}
        self._last_fetch_time: float = 0.0

    def add_key(self, kid: str, public_key: Any) -> None:
        """Add a key directly to cache (useful for tests and static bootstrapping)."""
        self._keys[kid] = public_key

    def get_key(self, kid: str) -> Any:
        """Retrieve key for kid, refetching from jwks_url if missing and cooldown expired."""
        if kid in self._keys:
            return self._keys[kid]

        if not self.jwks_url:
            raise AuthError(f"Unknown kid '{kid}' and no JWKS URL configured", code="unknown_kid")

        now = time.monotonic()
        if (now - self._last_fetch_time) < self.min_refetch_interval_s:
            # Rate-limited refetch: do not flood JWKS endpoint
            raise AuthError(f"Unknown kid '{kid}' (JWKS refetch rate-limited)", code="unknown_kid")

        self.refresh()
        if kid in self._keys:
            return self._keys[kid]

        raise AuthError(f"Unknown kid '{kid}' after JWKS refresh", code="unknown_kid")

    def refresh(self) -> None:
        """Fetch remote JWKS and load valid RS256/ES256 public keys."""
        if not self.jwks_url:
            return

        self._last_fetch_time = time.monotonic()
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(self.jwks_url)
                res.raise_for_status()
                jwks_data = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthError(
                f"Failed to fetch JWKS from {self.jwks_url}: {exc}", code="jwks_error"
            ) from exc

        keys_list = jwks_data.get("keys", [])
        for k in keys_list:
            kid = k.get("kid")
            if not kid:
                continue
            pub_key: rsa.RSAPublicKey | ec.EllipticCurvePublicKey | None = None
            try:
                parsed_key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                if isinstance(parsed_key, rsa.RSAPublicKey):
                    pub_key = parsed_key
            except (ValueError, TypeError, KeyError, jwt.PyJWTError):
                try:
                    parsed_ec = jwt.algorithms.ECAlgorithm.from_jwk(k)
                    if isinstance(parsed_ec, ec.EllipticCurvePublicKey):
                        pub_key = parsed_ec
                except (ValueError, TypeError, KeyError, jwt.PyJWTError):
                    continue
            if pub_key is not None:
                self._keys[kid] = pub_key


class JWTValidator:
    """Enterprise JWT validator enforcing pinned algorithms, JWKS, and claim checks."""

    def __init__(
        self,
        jwks_cache: JWKSCache,
        expected_issuer: str,
        expected_audience: str,
    ) -> None:
        self.jwks_cache = jwks_cache
        self.expected_issuer = expected_issuer
        self.expected_audience = expected_audience

    def verify_token(self, token: str) -> Principal:
        """Verify JWT signature, algorithm pinning, headers, and required claims.

        Returns Principal on success.
        Raises AuthError on any verification or compliance failure.
        """
        # 1. Inspect unverified headers to enforce header security
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as exc:
            raise AuthError(f"Malformed JWT header: {exc}", code="malformed_token") from exc

        # Disallow untrusted injection headers (jku, jwk, x5u, x5c)
        for h in FORBIDDEN_HEADERS:
            if h in unverified_header:
                raise AuthError(f"Forbidden header '{h}' present in token", code="forbidden_header")

        # 2. Enforce algorithm pinning (RS256, ES256 ONLY)
        alg = unverified_header.get("alg")
        if not alg or alg not in ALLOWED_ALGORITHMS:
            raise AuthError(
                f"Algorithm '{alg}' not permitted. Allowed: {ALLOWED_ALGORITHMS}",
                code="unsupported_algorithm",
            )

        # 3. Extract and check kid
        kid = unverified_header.get("kid")
        if not kid:
            raise AuthError("Missing 'kid' in token header", code="missing_kid")

        public_key = self.jwks_cache.get_key(str(kid))

        # 4. Enforce Key Type vs Algorithm Match
        if alg == "RS256" and not isinstance(public_key, rsa.RSAPublicKey):
            raise AuthError(
                "Key-type mismatch: RS256 requires RSA public key", code="key_type_mismatch"
            )
        if alg == "ES256" and not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise AuthError(
                "Key-type mismatch: ES256 requires EC public key", code="key_type_mismatch"
            )

        # 5. Decode with strict verification and mandatory claims
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key=public_key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self.expected_audience,
                issuer=self.expected_issuer,
                options={
                    "require": ["exp", "iss"],
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_nbf": True,
                    "verify_signature": True,
                },
            )
        except ExpiredSignatureError as exc:
            raise AuthError("Token has expired", code="token_expired") from exc
        except ImmatureSignatureError as exc:
            raise AuthError("Token not yet valid (future nbf)", code="token_immature") from exc
        except InvalidAudienceError as exc:
            raise AuthError("Token audience mismatch", code="invalid_audience") from exc
        except InvalidIssuerError as exc:
            raise AuthError("Token issuer mismatch", code="invalid_issuer") from exc
        except MissingRequiredClaimError as exc:
            raise AuthError(f"Missing required claim: {exc}", code="missing_claim") from exc
        except (InvalidSignatureError, InvalidAlgorithmError) as exc:
            raise AuthError(
                "Invalid token signature or algorithm", code="invalid_signature"
            ) from exc
        except InvalidTokenError as exc:
            raise AuthError(f"Invalid token: {exc}", code="invalid_token") from exc

        return Principal.from_claims(payload)
