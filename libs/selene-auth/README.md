# selene-auth

Shared authentication, JWT verification with algorithm pinning (RS256/ES256 only), RBAC dependencies, and fail-closed OPA client.

## Security Controls
- **Pinned Algorithms**: Rejects `none`, symmetric algorithms (`HS256`, `HS384`), and any algorithm outside `["RS256", "ES256"]`.
- **Confusion Defense**: Explicitly prevents public-key-as-HMAC key confusion attacks and enforces strict cryptographic key type to algorithm parity (RSA public key for RS256, EC public key for ES256).
- **Header Sanitization**: Ignores and rejects tokens containing injection headers (`jku`, `jwk`, `x5u`).
- **JWKS Protection**: Refetches keys solely from the configured JWKS endpoint with rate-limiting to prevent DoS floods on unknown `kid`.
- **Strict Claims**: Enforces presence and validity of `exp`, `iss`, `aud`, and `nbf`.
- **Principal Model**: Extracts roles, `org_id`, and verifies MFA claims (`amr`, `acr`).
- **Fail-Closed OPA**: Timeouts, network errors, or undefined policy results evaluate strictly to `allow=False`.
