from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from selene_auth.jwt import AuthError, JWKSCache, JWTValidator
from selene_auth.principal import Principal


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


@pytest.fixture(scope="module")
def ec_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key()


@pytest.fixture
def jwt_validator(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> JWTValidator:
    cache = JWKSCache(
        preloaded_keys={
            "rsa-key-1": rsa_keypair[1],
            "ec-key-1": ec_keypair[1],
        }
    )
    return JWTValidator(
        jwks_cache=cache,
        expected_issuer="https://auth.selene.local/realms/selene",
        expected_audience="selene-api",
    )


def test_valid_rs256_token(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-uuid-123",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "roles": ["analyst"],
        "org_id": "org-456",
        "amr": ["pwd", "webauthn"],
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    principal = jwt_validator.verify_token(token)
    assert principal.sub == "user-uuid-123"
    assert principal.roles == ["analyst"]
    assert principal.org_id == "org-456"
    assert principal.mfa_verified is True


def test_valid_es256_token(
    jwt_validator: JWTValidator,
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "service-client-789",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "roles": ["service"],
    }
    token = jwt.encode(payload, ec_keypair[0], algorithm="ES256", headers={"kid": "ec-key-1"})

    principal = jwt_validator.verify_token(token)
    assert principal.sub == "service-client-789"
    assert principal.roles == ["service"]
    assert principal.mfa_verified is False


def test_tampered_jwt_signature_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-uuid-123",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    # Tamper with payload segment
    parts = token.split(".")
    tampered_token = f"{parts[0]}.eyJhZG1pbiI6dHJ1ZX0.{parts[2]}"

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(tampered_token)
    assert exc.value.code in {"invalid_signature", "invalid_token", "missing_claim"}


def test_alg_none_rejected(jwt_validator: JWTValidator) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-uuid-123",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    # Forge alg=none token
    token = jwt.encode(payload, key="", algorithm="none", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "unsupported_algorithm"


def test_hs256_public_key_confusion_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    """Attacker crafts an HS256 token signed using the server's RSA public key as HMAC secret."""
    import base64
    import hashlib
    import hmac
    import json

    from cryptography.hazmat.primitives import serialization

    now = datetime.now(UTC)
    payload = {
        "sub": "attacker-sub",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    pub_pem = rsa_keypair[1].public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    header_b64 = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "kid": "rsa-key-1"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature_b64 = (
        base64.urlsafe_b64encode(hmac.new(pub_pem, signing_input, hashlib.sha256).digest())
        .rstrip(b"=")
        .decode()
    )
    forged_token = f"{header_b64}.{payload_b64}.{signature_b64}"

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(forged_token)
    assert exc.value.code == "unsupported_algorithm"


def test_key_type_alg_mismatch_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    """Token specifies ES256 but points to an RSA key in the JWKS."""
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    # Token claiming ES256 with kid pointing to rsa-key-1
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    # Manually tamper header to declare ES256
    import base64
    import json

    header = json.dumps({"alg": "ES256", "kid": "rsa-key-1"}).encode("utf-8")
    header_b64 = base64.urlsafe_b64encode(header).rstrip(b"=").decode("utf-8")
    parts = token.split(".")
    mismatched_token = f"{header_b64}.{parts[1]}.{parts[2]}"

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(mismatched_token)
    assert exc.value.code == "key_type_mismatch"


def test_missing_exp_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "missing_claim"


def test_missing_iss_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "missing_claim"


def test_future_nbf_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "nbf": int((now + timedelta(minutes=2)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "token_immature"


def test_expired_token_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    past = datetime.now(UTC) - timedelta(minutes=10)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((past + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "token_expired"


def test_wrong_audience_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "wrong-audience",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "invalid_audience"


def test_unknown_kid_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(
        payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "non-existent-kid"}
    )

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "unknown_kid"


def test_forbidden_injection_headers_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    # Injected jku header
    token = jwt.encode(
        payload,
        rsa_keypair[0],
        algorithm="RS256",
        headers={"kid": "rsa-key-1", "jku": "https://attacker.com/jwks.json"},
    )

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "forbidden_header"


def test_jwks_cache_rate_limits_refetch_on_unknown_kid() -> None:
    cache = JWKSCache(
        jwks_url="https://auth.selene.local/protocol/openid-connect/certs",
        min_refetch_interval_s=5.0,
    )
    # Simulate first fetch recorded recently
    cache._last_fetch_time = time.monotonic()

    with pytest.raises(AuthError) as exc:
        cache.get_key("unseen-kid")
    assert "rate-limited" in exc.value.message


def test_jwks_cache_remote_fetch_success(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    from unittest.mock import MagicMock, patch

    # Export RSA public key to JWK format
    jwk_dict = jwt.algorithms.RSAAlgorithm.to_jwk(rsa_keypair[1], as_dict=True)
    jwk_dict["kid"] = "remote-rsa-kid"

    cache = JWKSCache(
        jwks_url="https://auth.selene.local/protocol/openid-connect/certs",
        min_refetch_interval_s=0.0,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"keys": [jwk_dict]}

    with patch("httpx.Client.get", return_value=mock_resp):
        key = cache.get_key("remote-rsa-kid")
        assert key is not None
        assert isinstance(key, rsa.RSAPublicKey)


def test_jwks_cache_remote_fetch_network_failure() -> None:
    from unittest.mock import patch

    cache = JWKSCache(
        jwks_url="https://auth.selene.local/protocol/openid-connect/certs",
        min_refetch_interval_s=0.0,
    )

    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Network unreachable")):
        with pytest.raises(AuthError) as exc:
            cache.get_key("some-kid")
        assert exc.value.code == "jwks_error"


def test_principal_from_claims_variations() -> None:
    # Test realm_access format, string amr, and acr levels
    claims = {
        "sub": "user-uuid",
        "realm_access": {"roles": ["operator", "auditor"]},
        "amr": "otp",
        "acr": "level2",
        "email": "user@selene.local",
    }
    p = Principal.from_claims(claims)
    assert p.sub == "user-uuid"
    assert "operator" in p.roles
    assert "auditor" in p.roles
    assert p.mfa_verified is True
    assert p.email == "user@selene.local"


def test_principal_from_claims_mfa_absent_defaults_false() -> None:
    claims = {
        "sub": "user-without-mfa",
        "roles": ["analyst"],
    }
    p = Principal.from_claims(claims)
    assert p.sub == "user-without-mfa"
    assert p.mfa_verified is False


def test_malformed_token_header_rejected(jwt_validator: JWTValidator) -> None:
    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token("not-a-valid.jwt-token.at-all")
    assert exc.value.code == "malformed_token"


def test_token_missing_kid_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    # Token without 'kid' in header
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "missing_kid"


def test_key_type_alg_mismatch_rs256_with_ec_key(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    # Validator cache where kid is mapped to an EC public key
    cache = JWKSCache(preloaded_keys={"mixed-key": ec_keypair[1]})
    validator = JWTValidator(
        jwks_cache=cache,
        expected_issuer="https://auth.selene.local/realms/selene",
        expected_audience="selene-api",
    )
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://auth.selene.local/realms/selene",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "mixed-key"})

    with pytest.raises(AuthError) as exc:
        validator.verify_token(token)
    assert exc.value.code == "key_type_mismatch"
    assert "RS256 requires RSA public key" in exc.value.message


def test_token_invalid_issuer_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "iss": "https://evil.attacker.org/realms/evil",
        "aud": "selene-api",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_keypair[0], algorithm="RS256", headers={"kid": "rsa-key-1"})

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(token)
    assert exc.value.code == "invalid_issuer"


def test_generic_invalid_token_rejected(
    jwt_validator: JWTValidator,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    # Valid base64 header
    header_b64 = (
        base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"rsa-key-1"}').rstrip(b"=").decode()
    )
    # Valid base64, but invalid JSON content
    payload_b64 = base64.urlsafe_b64encode(b"not valid json {").rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = rsa_keypair[0].sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    bad_token = f"{header_b64}.{payload_b64}.{sig_b64}"

    with pytest.raises(AuthError) as exc:
        jwt_validator.verify_token(bad_token)
    assert exc.value.code == "invalid_token"


def test_jwks_cache_remote_fetch_ec_and_unsupported_keys(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    from unittest.mock import MagicMock, patch

    ec_jwk = jwt.algorithms.ECAlgorithm.to_jwk(ec_keypair[1], as_dict=True)
    ec_jwk["kid"] = "remote-ec-kid"

    cache = JWKSCache(
        jwks_url="https://auth.selene.local/protocol/openid-connect/certs",
        min_refetch_interval_s=0.0,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "keys": [
            ec_jwk,
            {"kty": "RSA"},  # Missing kid -> continue
            {"kid": "unsupported-oct", "kty": "oct", "k": "c2VjcmV0"},  # Unsupported -> continue
        ]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        key = cache.get_key("remote-ec-kid")
        assert key is not None
        assert isinstance(key, ec.EllipticCurvePublicKey)


def test_jwks_cache_add_key_and_no_url() -> None:
    cache = JWKSCache()
    cache.add_key("custom-kid", "dummy-key")
    assert cache.get_key("custom-kid") == "dummy-key"

    # refresh with no url returns None
    assert cache.refresh() is None


def test_jwks_cache_unknown_kid_after_refresh() -> None:
    from unittest.mock import MagicMock, patch

    cache = JWKSCache(
        jwks_url="https://auth.selene.local/protocol/openid-connect/certs",
        min_refetch_interval_s=0.0,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"keys": []}

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(AuthError) as exc:
            cache.get_key("missing-kid-after-refresh")
        assert exc.value.code == "unknown_kid"
        assert "after JWKS refresh" in exc.value.message
