# Keycloak realm directory

Phase 0 Task 0.3 adds `selene-realm.json` here (roles, clients, mappers, MFA requirement, token lifetimes, fake dev users). Docker Compose mounts this directory into Keycloak with `--import-realm`. Never commit real secrets or real user data here.
