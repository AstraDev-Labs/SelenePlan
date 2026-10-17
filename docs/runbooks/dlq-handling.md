# Runbook: Dead Letter Queue (DLQ) Inspection and Replay

## 1. Overview
Asynchronous tasks in SelenePlan—such as terrain rasterization, illumination timestack generation, comms line-of-sight checks, and hazard ML tile inference—are driven by Apache Kafka topics.

When a message repeatedly fails processing (exceeds max retry count, encounters a permanent schema mismatch, or runs out of execution memory), the worker intercepts the exception, attaches troubleshooting metadata headers, and redirects the message to a Dead Letter Queue (`<topic-name>.dlq`).

## 2. Alerts and Thresholds
- **Alert Name:** `DLQMessageGrowth`
- **Prometheus Metric:** `sum(kafka_topic_partition_current_offset{topic=~".*\\.dlq"}) by (topic) > 0`
- **Severity:** WARNING (escalates to HIGH if message count > 20 within 1 hour)

## 3. DLQ Message Inspection
1. **Identify Affected Queue:**
   Check Prometheus or run Kafka topic inspection:
   ```bash
   kubectl exec -it kafka-0 -n selene-storage -- kafka-consumer-groups.sh \
     --bootstrap-server localhost:9092 \
     --describe --group selene-workers
   ```
2. **Inspect DLQ Payload and Headers:**
   Consume without committing offset or using a dedicated inspection tool:
   ```bash
   python -m tools.inspect_dlq \
     --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" \
     --topic "pipeline.step.request.dlq" \
     --max-messages 5
   ```
   Inspect standard headers:
   - `x-death-reason`: Exception class and summary (e.g., `TerrainTileMissingError`, `RasterDimensionMismatchError`).
   - `x-original-topic`: Source topic (e.g., `pipeline.step.request`).
   - `x-retry-count`: Number of failed attempts prior to DLQ routing.
   - `x-trace-id`: Distributed trace ID for OpenTelemetry correlation.
   - `x-failed-timestamp`: ISO 8601 UTC failure time.

## 4. Root Cause Analysis Checklist
- **Transient Dependency Outage:** Did MinIO, PostgreSQL, or SPICE service experience high latency or restart during the event?
- **Invalid Payload / Corrupted Input:** Does the payload point to a deleted or non-existent DEM artifact hash?
- **Out of Memory (OOM):** Did worker pods get killed by Kubernetes OOMKiller (`dmesg` / `kubectl describe pod`)?
- **Schema Evolution:** Did a recent service deployment introduce an unhandled enum or field version?

## 5. Replay Procedure
Once the underlying defect, dependency, or configuration is fixed:

1. **Dry-Run Replay:**
   Validate that the candidate messages will parse cleanly against the current schema:
   ```bash
   python -m tools.replay_dlq \
     --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" \
     --topic "pipeline.step.request.dlq" \
     --dry-run
   ```
2. **Execute Replay:**
   Move messages from the DLQ back to their primary destination topic with preserved trace IDs:
   ```bash
   python -m tools.replay_dlq \
     --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" \
     --topic "pipeline.step.request.dlq" \
     --target-topic "pipeline.step.request" \
     --commit
   ```
3. **Monitor Ingestion & Worker Telemetry:**
   Observe Grafana dashboard `SelenePlan Mission Control` -> `Kafka Consumer Lag & Throughput` to ensure the replayed messages process successfully and do not bounce back into DLQ.

## 6. Poison Pill Quarantine
If a specific message is permanently malformed and cannot be reprocessed:
1. Export raw message payload to the quarantine archive bucket:
   ```bash
   python -m tools.quarantine_dlq \
     --topic "pipeline.step.request.dlq" \
     --offset 1042 \
     --s3-bucket "selene-quarantine"
   ```
2. Acknowledge and advance DLQ consumer group offset.
3. Log audit event detailing why message was quarantined.
