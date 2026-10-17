# Runbook: Vault Transit Key Rotation for SelenePlan

## 1. Overview
The signing key `selene-plan-signing` is an Ed25519 asymmetric key stored within HashiCorp Vault Transit engine. It is utilized exclusively by `signing-service` to generate cryptographic signatures over RFC 8785 canonical plan payloads.

## 2. Rotation Policy
- **Cadence:** Rotate quarterly or immediately following any suspected compromise.
- **Backward Compatibility:** Older key versions are retained in a retired state. Signatures produced under older versions remain fully verifiable indefinitely.

## 3. Rotation Procedure

### Automated / API Trigger
To rotate the key version:
```bash
curl -X POST https://signing-service.internal:8110/internal/v1/keys/rotate \
  -H "Authorization: Bearer <mTLS-service-token>"
```
Response:
```json
{
  "status": "rotated",
  "key_id": "selene-plan-signing",
  "new_active_version": 2
}
```

### Vault CLI Trigger
```bash
vault write -f transit/keys/selene-plan-signing/rotate
```

## 4. Verification After Rotation
1. Verify key metadata lists the new active version and the older version as retired:
   ```bash
   curl https://signing-service.internal:8110/v1/keys
   ```
2. Verify that existing signed plans still verify:
   ```bash
   python tools/verify_bundle.py path/to/historical_plan_bundle.json
   ```
3. Issue a new test signature and verify it uses the new active version.
