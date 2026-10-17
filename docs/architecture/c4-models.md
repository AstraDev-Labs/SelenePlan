# Architecture: C4 Model Diagrams for SelenePlan

This document contains C4 architecture models (Context, Container, and Component levels) for SelenePlan expressed in standard Mermaid syntax.

---

## 1. Level 1: System Context Diagram

The System Context diagram illustrates how external users (Analyst, Approver, Auditor) and external systems interact with the SelenePlan platform.

```mermaid
C4Context
    title System Context Diagram for SelenePlan Lunar South Pole Mission Planner

    Person(analyst, "Mission Analyst", "Configures AOI, initiates multi-layer terrain/solar/comms analysis, explores candidate sites, and generates traverse paths.")
    Person(approver, "Mission Approver", "Conducts two-person four-eyes review and grants cryptographic sign-off for planned lunar traverses.")
    Person(auditor, "Mission Auditor", "Verifies cryptographic bundles, inspects immutable audit logs, and validates deterministic reproduction.")

    Enterprise_Boundary(b0, "SelenePlan Mission Platform") {
        System(seleneplan, "SelenePlan System", "Autonomous lunar south pole landing site selection, time-expanded traverse planning, explainability engine, and cryptographic audit registry.")
    }

    System_Ext(pds, "NASA PDS / Geoscience", "Public repository hosting LOLA DEMs, LROC imagery, and planetary ephemerides.")
    System_Ext(vault, "HashiCorp Vault", "Hardware Security Module / Transit engine managing Ed25519 asymmetric keys.")
    System_Ext(keycloak, "Keycloak / OIDC Identity", "Enterprise identity provider issuing signed JWTs with MFA claims.")

    Rel(analyst, seleneplan, "Uses web UI / REST APIs to plan traverses", "HTTPS/TLS 1.3")
    Rel(approver, seleneplan, "Reviews constraints and signs approvals", "HTTPS/mTLS + MFA")
    Rel(auditor, seleneplan, "Audits event hash chain and verifies bundles", "HTTPS / CLI")

    Rel(seleneplan, pds, "Ingests lunar terrain and ephemeris datasets", "HTTPS / Allowlisted Host")
    Rel(seleneplan, vault, "Requests RFC 8785 canonical plan signing", "mTLS")
    Rel(seleneplan, keycloak, "Validates OIDC tokens and MFA roles", "OAuth2 / OIDC")
```

---

## 2. Level 2: Container Diagram

The Container diagram breaks down SelenePlan into its high-level microservices, data stores, and event brokers.

```mermaid
C4Container
    title Container Diagram for SelenePlan Microservices Architecture

    Person(user, "Mission Operator", "Analyst, Approver, or Auditor")

    Container_Boundary(c0, "SelenePlan Platform Boundary") {
        Container(web, "Web Application", "React, TypeScript, Vite, TailwindCSS", "Provides interactive lunar 2D/3D map viewport, dual timelines, traverse charts, and approval panels.")
        Container(gateway, "API Gateway", "FastAPI / Kong / Envoy", "Terminates mTLS, validates JWTs, applies rate limits, and routes requests.")

        Container(project_svc, "project-service", "Python, FastAPI, SQLAlchemy", "Orchestrates multi-phase analysis workflows, manages project state machines, and enforces four-eyes approvals.")
        Container(planner_svc, "planner-service", "Python, NumPy, NetworkX", "Site ranking via soft scoring, time-expanded A* traverse search, and contrastive what-if explanations.")
        Container(hazard_svc, "hazard-ml-service", "Python, ONNX Runtime, OpenCV", "Tiled crater and rock detection using signed ONNX models, circular NMS deduplication, and hazard fusion.")
        Container(illum_svc, "illumination-service", "Python, selene-horizon, SPICE", "Horizon elevation profiling, SPICE Sun ephemerides, and Zarr timestack solar availability computation.")
        Container(comms_svc, "comms-service", "Python, selene-geo, SPICE", "Earth line-of-sight raytracing, libration modeling, and communication contact window extraction.")
        Container(terrain_svc, "terrain-service", "Python, selene-geo, GDAL", "Cloud-Optimized GeoTIFF sampling, slope calculation in radians, and roughness estimation.")
        Container(signing_svc, "signing-service", "Python, cryptography, RFC 8785", "Canonicalizes plan JSON payloads and produces Ed25519 cryptographic signatures via Vault Transit.")
        Container(audit_svc, "audit-service", "Python, FastAPI, PostgreSQL", "Maintains tamper-evident SHA-256 hash-chained audit log with periodic WORM S3 anchoring.")
        Container(report_svc, "report-service", "Python, Jinja2, WeasyPrint", "Generates verifiable HTML/PDF mission briefing packets, GeoJSON layers, and CSV waypoints.")
        Container(prov_svc, "provenance-service", "Python, FastAPI, NetworkX", "Records directed acyclic graph (DAG) data lineage and verifies artifact integrity.")

        ContainerDb(pg, "PostgreSQL 16", "Relational Database", "Stores projects, state machines, user actions, and audit hash chain.")
        ContainerDb(s3, "MinIO / S3", "Object Storage", "Stores terrain COGs, Zarr illumination timestacks, crater rasters, and signed report bundles.")
        ContainerDb(kafka, "Apache Kafka", "Message Broker", "Decouples asynchronous analysis requests, step progress updates, and audit events.")
    }

    Rel(user, web, "Interacts with", "HTTPS")
    Rel(web, gateway, "API Requests", "HTTPS/JSON")
    Rel(gateway, project_svc, "Routes to", "Internal mTLS")
    Rel(gateway, planner_svc, "Routes to", "Internal mTLS")
    Rel(project_svc, kafka, "Publishes analysis tasks", "SASL_PLAINTEXT")
    Rel(kafka, illum_svc, "Consumes step requests", "SASL_PLAINTEXT")
    Rel(kafka, comms_svc, "Consumes step requests", "SASL_PLAINTEXT")
    Rel(kafka, hazard_svc, "Consumes step requests", "SASL_PLAINTEXT")
    Rel(kafka, terrain_svc, "Consumes step requests", "SASL_PLAINTEXT")
    Rel(project_svc, signing_svc, "Requests signature upon approval", "mTLS")
    Rel(project_svc, report_svc, "Requests bundle generation", "mTLS")
    Rel(project_svc, audit_svc, "Emits audit.event", "mTLS / Kafka")
    Rel(all, prov_svc, "Registers lineage nodes", "mTLS")
    Rel(all, pg, "Reads/Writes relational state", "SQL / TLS")
    Rel(all, s3, "Reads/Writes rasters and arrays", "S3 API / TLS")
```

---

## 3. Level 3: Component Diagram – Planner Service

The Component diagram details the internal software architecture of `services/planner-service/`.

```mermaid
C4Component
    title Component Diagram for Planner Service

    Container_Boundary(c1, "planner-service Boundary") {
        Component(api, "REST Controller", "FastAPI Router", "Exposes /v1/rank-sites, /v1/traverses/plan, /v1/traverses/compare, and /v1/traverses/explain.")
        Component(energy, "Rover Energy Model", "Pure Python Function", "Computes solar power generation $P_{solar}(t)$, drive power consumption $P_{drive}(v, \alpha)$, and battery state-of-charge $E(t)$.")
        Component(site_rank, "Site Candidate Ranker", "NumPy / Soft Scoring", "Scores landing sites by weighted sum of cumulative illumination, Earth visibility, terrain flatness, and hazard clearance.")
        Component(astar, "Time-Expanded A* Search", "NetworkX / Priority Queue", "Explores space-time nodes $(x, y, t)$ to find optimal traverses respecting slope, solar charging, and comms windows.")
        Component(whatif, "Contrastive Explainer", "Rule Engine / Diff Evaluator", "Evaluates alternative routes against constraints and generates structured natural-language rejection rationales.")
    }

    Rel(api, site_rank, "Invokes site candidate ranking", "Python Calls")
    Rel(api, astar, "Invokes traverse path solver", "Python Calls")
    Rel(api, whatif, "Invokes contrastive explanations", "Python Calls")
    Rel(astar, energy, "Evaluates battery delta on each edge", "Pure Function")
    Rel(whatif, astar, "Computes alternative paths under counterfactuals", "Python Calls")
```

---

## 4. Level 3: Component Diagram – Project Service

The Component diagram details the orchestrator and approval engine within `services/project-service/`.

```mermaid
C4Component
    title Component Diagram for Project Service

    Container_Boundary(c2, "project-service Boundary") {
        Component(proj_api, "Project Controller", "FastAPI Router", "Manages project lifecycle, AOI creation, and workflow triggers.")
        Component(sm, "Orchestrator State Machine", "Pure Function Engine", "Maintains deterministic state transitions: CREATED -> RUNNING -> COMPLETED with join-barrier synchronization.")
        Component(workflow, "Four-Eyes Approval Engine", "Business Logic", "Enforces distinct non-creator approver roles, MFA token validation, and multi-signature collection.")
        Component(policy_agent, "OPA Policy Client", "HTTP / Embedded Rego", "Evaluates policies/plan_workflow.rego to authorize plan submission and approvals.")
        Component(event_pub, "Audit & Kafka Dispatcher", "selene-events", "Publishes state change events and audit records.")
    }

    Rel(proj_api, sm, "Updates pipeline execution state", "Function Calls")
    Rel(proj_api, workflow, "Submits and processes approval votes", "Function Calls")
    Rel(workflow, policy_agent, "Verifies policy constraints", "REST / JSON")
    Rel(workflow, event_pub, "Emits audit.event and plan.approved", "Event Bus")
```
