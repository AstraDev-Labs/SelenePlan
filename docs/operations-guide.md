# SelenePlan Operations Guide

## 1. System Architecture & Topology
SelenePlan is deployed as an event-driven microservice system partitioned across four logical Kubernetes tiers:
1. **Core Gateway & Ingress Tier (`selene-core`):** API Gateway (Port 8000), Keycloak Identity (Port 8080), Web Frontend (Port 80).
2. **Analysis Tier (`selene-analysis`):** Terrain Service (8103), Illumination Engine (8105), Comms Service (8106), Hazard ML Service (8104), Ingestion Service (8102).
3. **Planning & Governance Tier (`selene-planning`):** Project Service (8101), Planner Service (8107), Signing Service (8110), Report Service (8108), Provenance Service (8111), Audit Service (8109).
4. **Storage & Infrastructure Tier (`selene-storage`):** PostgreSQL 16 (Port 5432), MinIO Object Storage (Ports 9000/9001), Apache Kafka + Zookeeper (Port 9092), HashiCorp Vault (Port 8200).

---

## 2. Configuration & Environment Variables

| Variable | Scope | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Global | Runtime environment (`development`, `staging`, `production`) | `production` |
| `DATABASE_URL` | Services | PostgreSQL connection string with TLS | `postgresql://selene:***@postgres:5432/selenedb` |
| `KAFKA_BOOTSTRAP_SERVERS` | Services | Kafka broker endpoints | `kafka.selene-storage.svc:9092` |
| `S3_ENDPOINT_URL` | Services | S3 / MinIO endpoint | `http://minio.selene-storage.svc:9000` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Services | Object storage credentials (Vault injected) | Injected via Secret |
| `VAULT_ADDR` | Signing | HashiCorp Vault server address | `https://vault.selene-storage.svc:8200` |
| `VAULT_TOKEN` | Signing | Vault Transit engine service token | Injected via Secret |
| `KEYCLOAK_URL` | Auth / Web | Keycloak OIDC issuer URL | `http://identity:8080/realms/selene` |
| `ALLOWED_INGESTION_HOSTS` | Ingestion | Whitelist of outbound DEM ingestion hosts | `pgda.gsfc.nasa.gov,pds-geosciences.wustl.edu` |

---

## 3. Deployment Procedures

### 3.1 Local Development (Docker Compose)
For local development, testbed simulations, and smoke testing:
```bash
# 1. Copy sample environment
cp infra/.env.example infra/.env

# 2. Launch background infrastructure and microservices
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d

# 3. Verify health status
curl http://localhost:8000/healthz
```

### 3.2 Production Kubernetes Deployment (Helm)
Production deployments utilize the umbrella Helm chart located in `infra/helm/seleneplan`:
```bash
# 1. Add secret values from Vault
helm upgrade --install seleneplan infra/helm/seleneplan \
  --namespace selene-production \
  --create-namespace \
  --values infra/helm/seleneplan/values.yaml \
  --values infra/helm/seleneplan/values-production.yaml

# 2. Verify all pods are running under Restricted Pod Security Standard
kubectl get pods -n selene-production
```

---

## 4. Observability & Monitoring

### 4.1 Prometheus Alerting Rules
Configured in `infra/monitoring/alerts/selene-alerts.yaml`:
- `AuditChainTamperDetected`: Immediate notification if audit hash sequence diverges.
- `AuthAnomalySpike`: Alerts on high rates of authentication / MFA failures ($> 5/\text{sec}$).
- `DLQMessageGrowth`: Alerts when messages accumulate in any `*.dlq` topic.
- `SLOP95LatencyBreached`: Alerts when plan computation p95 latency exceeds 5 seconds.

### 4.2 Grafana Mission Control Dashboard
Located in `infra/monitoring/dashboards/selene-mission-control.json`:
- Real-time Kafka consumer group lag per analysis service.
- Worker execution duration percentiles (p50, p90, p99).
- Vault Transit signing request latencies.
- Real-time audit chain verification status indicator.

---

## 5. Operations & Incident Runbooks
For operational drills, incidents, and administrative workflows, refer to the dedicated runbooks:
- **Audit Integrity Incident Response:** [`docs/runbooks/audit-integrity-incident.md`](file:///docs/runbooks/audit-integrity-incident.md)
- **Dead Letter Queue (DLQ) Handling:** [`docs/runbooks/dlq-handling.md`](file:///docs/runbooks/dlq-handling.md)
- **Backup & Disaster Recovery Drill:** [`docs/runbooks/restore.md`](file:///docs/runbooks/restore.md)
- **Cluster Scaling & Capacity:** [`docs/runbooks/scaling.md`](file:///docs/runbooks/scaling.md)
- **Key Rotation (Vault Transit):** [`docs/runbooks/key-rotation.md`](file:///docs/runbooks/key-rotation.md)
- **Dataset Onboarding & CRS Validation:** [`docs/runbooks/dataset-onboarding.md`](file:///docs/runbooks/dataset-onboarding.md)
- **Release & Deployment Procedure:** [`docs/runbooks/release-procedure.md`](file:///docs/runbooks/release-procedure.md)
