# Runbook: Cluster Scaling and Capacity Management

## 1. Overview
SelenePlan operates under two distinct workload patterns:
1. **Interactive API & UI Services:** Low latency, steady-state HTTP request/response loads (`web`, `project-service`, `planner-service`, `signing-service`, `report-service`).
2. **Analysis Workers & Pipelines:** High-throughput, CPU- and memory-intensive batch processing driven by Kafka (`terrain-service`, `illumination-service`, `comms-service`, `hazard-ml-service`).

Scaling is automated through a hybrid combination of **Horizontal Pod Autoscalers (HPA)** for HTTP APIs and **Kubernetes Event-driven Autoscaling (KEDA)** for Kafka event workers.

## 2. Autoscaling Architecture & Configuration

### A. Worker Autoscaling (KEDA)
Workers scale dynamically based on the queue depth (consumer group lag) on their designated Kafka partition:
- **Metrics Trigger:** `kafka` trigger evaluating `consumerGroup: selene-<service>-group`.
- **Lag Threshold:** 5 messages per worker replica.
- **Min / Max Replicas:** 2 min, 12 max.
- **Cooldown Window:** 300 seconds (prevents rapid flapping during burst processing).

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: illumination-worker-scaler
  namespace: selene-analysis
spec:
  scaleTargetRef:
    name: illumination-service
  minReplicaCount: 2
  maxReplicaCount: 12
  cooldownPeriod: 300
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka.selene-storage.svc.cluster.local:9092
        consumerGroup: selene-illumination-group
        topic: pipeline.step.illumination
        lagThreshold: "5"
```

### B. HTTP API Autoscaling (HPA)
HTTP services scale based on CPU and memory utilization:
- **CPU Target:** 70% average utilization.
- **Memory Target:** 80% average utilization.
- **Min / Max Replicas:** 2 min, 8 max.

## 3. Capacity & Node Pool Sizing

| Workload Tier | Node Pool Type | vCPU / RAM per Pod | Target Node Profile | Max Scale |
| :--- | :--- | :--- | :--- | :--- |
| **API Tier** (`selene-core`, `web`) | General Purpose | 500m / 512Mi | `c6i.xlarge` (4 vCPU, 8 GB) | 8 replicas |
| **Hazard ML Inference** (`hazard-ml`) | Compute Optimized | 2000m / 4Gi | `c6i.2xlarge` (8 vCPU, 16 GB) | 8 replicas |
| **Illumination Timestack** (`illumination`) | Memory Optimized | 2000m / 8Gi | `r6i.2xlarge` (8 vCPU, 64 GB) | 12 replicas |
| **Comms LOS Raytracing** (`comms`) | Compute Optimized | 2000m / 4Gi | `c6i.2xlarge` (8 vCPU, 16 GB) | 8 replicas |

## 4. Operational Troubleshooting

### Problem 1: Worker Scale-Up Flapping / Thrashing
- **Symptom:** Worker pod count jumps between 2 and 10 every few minutes.
- **Diagnosis:** Batch analysis tasks publish 20 messages simultaneously; once consumed, lag drops to 0 before the cooldown window finishes.
- **Resolution:**
  1. Increase `cooldownPeriod` in `ScaledObject` to `600s`.
  2. Implement KEDA `stabilizationWindowSeconds` under `behavior.scaleDown`.

### Problem 2: Database Connection Pool Saturation
- **Symptom:** As worker count scales up to 30+ total pods across the cluster, PostgreSQL logs `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
- **Diagnosis:** Each worker pod instantiates an independent connection pool of 10 connections.
- **Resolution:**
  1. Route all database connections through `PgBouncer` connection pooler in transaction pooling mode.
  2. Set `max_client_conn = 1000`, `default_pool_size = 50`.
  3. Ensure application services configure `pool_size = 5`, `max_overflow = 5`.

### Problem 3: Cluster Autoscaler / Node Quota Starvation
- **Symptom:** Pods remain stuck in `Pending` state with event `0/6 nodes are available: Insufficient cpu`.
- **Diagnosis:** Kubernetes Cluster Autoscaler reached cloud provider cloud quota limits for the compute pool.
- **Resolution:**
  1. Verify pending pods: `kubectl get pods -A --field-selector=status.phase=Pending`.
  2. Check cluster autoscaler logs: `kubectl logs -n kube-system deployment/cluster-autoscaler`.
  3. Temporarily clamp worker `maxReplicaCount` in KEDA until cloud provider vCPU quota increase is granted.
