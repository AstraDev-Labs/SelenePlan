# identity

**Port:** 8081
**Tech:** Keycloak with realm `selene`
**Phase:** 0

## Purpose
Centralized authentication, role assignment, MFA enforcement (for approvers and admins), and token issuance (SEC-01, C-AUTH-1).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/identity/SPEC.md) for realm configuration, client definitions, and seed credentials.

## Roles
- `analyst`, `operator`, `approver`, `steward`, `admin`, `auditor`.

## Seed Users (Dev Only)
Documented dev user accounts with fake credentials live in the imported realm configuration at [services/identity/realm/selene-realm.json](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/identity/realm/selene-realm.json).
