# Novelty Statement and Prior-Art Comparison

## 1. The Precise Claim to Defend
SelenePlan defends the following novel contribution in space systems and mission engineering:

> **A time-aware joint optimization architecture that co-optimizes rover traverses across dynamic lunar illumination, time-varying Earth line-of-sight communication visibility, terrain slope hazards, and state-of-charge battery dynamics, coupled with a contrastive explainability engine that computes natural-language constraint violation rationales, encapsulated entirely within a cryptographic zero-trust mission integrity boundary (four-eyes approval, RFC 8785 Ed25519 plan signing, SHA-256 hash-chained audit logging, and signed model registries).**

---

## 2. Comparative Analysis with Prior Art

| Capability / Attribute | Traditional Planetary GIS (e.g., QGIS / ArcGIS Lunar) | Mission Planners (e.g., NASA VIPER / JPL RSVP) | Academic Research Planners (A* / RRT* on DEM) | **SelenePlan Platform** |
| :--- | :--- | :--- | :--- | :--- |
| **Lunar Geodesy ($R = 1,737.4\text{ km}$)** | Partial (requires manual CRS configuration) | Full (custom mission frame) | Often neglected (flat Earth / WGS84 bugs) | **Enforced natively in core types (`selene-geo`)** |
| **Dynamic Grazing Illumination** | Static hillshade only | Pre-computed static rasters | Often ignored | **720-step azimuthal horizon raytracing + SPICE** |
| **Earth Libration & LOS Visibility** | Not modeled | Separate comms team tool | Not integrated | **Jointly co-optimized in space-time graph** |
| **Battery State-of-Charge Dynamics** | None | Separate power subsystem simulator | Simplified distance penalty | **Pure-function power-generation & drive model** |
| **Explainability Engine** | None | Manual operator inspection | Cost metric only | **Contrastive counterfactual explanations** |
| **Four-Eyes Governance** | None | Administrative procedures | None | **Automated OPA Rego policy + MFA gates** |
| **Cryptographic Tamper-Evidence** | None | File checksums | None | **RFC 8785 JCS + Ed25519 digital signatures** |
| **Audit Forensics** | Standard DB logging | Mission log files | None | **SHA-256 cryptographic hash chain + WORM S3** |
| **Deterministic Replay** | Manual | Difficult across software versions | Undefined | **Lineage-driven bit-exact replay CLI tool** |

---

## 3. Detailed Novel Elements

### 3.1 Joint Space-Time Co-Optimization
Existing planetary rover operations decompose planning into sequential silos: terrain specialists filter slope, power engineers inspect solar tables, comms engineers calculate direct-to-Earth windows, and planners generate paths on static cost maps.
SelenePlan eliminates these silos by formulating traverse planning directly as a **time-expanded graph search** $(x, y, t)$ where the state transition function $f(s, a)$ couples:
- Solar incidence angle $\theta_{sun}(x, y, t)$ and panel generation $P_{solar}(t)$.
- Topographic slope $\alpha(x, y)$ and drive energy consumption $P_{drive}(\alpha, v)$.
- Line-of-sight elevation $\theta_{earth}(x, y, t)$ and required comms passes.
- Battery energy state $E(t) \ge E_{reserve}$.

### 3.2 Contrastive Counterfactual Explainability
When human flight directors review a proposed route, the critical operational question is not merely *"Why is this route optimal?"* but *"Why did the system reject the intuitive or shorter alternative?"*.
SelenePlan implements a **contrastive explainability engine** that evaluates counterfactual routes (such as direct straight-line chords or alternative saddle points) against the multi-physics constraint space, pinpointing the exact spatial coordinate and time interval where a failure occurs (e.g. *"Shadow from 14:00 to 19:00 induces 0% SOC at km 1.2"*).

### 3.3 Cryptographic Non-Repudiation for Autonomous Space Systems
As space exploration transitions to autonomous or semi-autonomous mission planning, the risk of data poisoning, unauthorized plan alteration, or model supply-chain tampering creates existential mission safety hazards.
SelenePlan integrates cryptographic verification into every state transition:
1. Plans are canonicalized via RFC 8785 and signed via Vault Transit Ed25519 keys only after two distinct approvers provide valid MFA signatures.
2. The audit log enforces non-repudiation using a continuous cryptographic SHA-256 hash chain anchored daily to immutable WORM object storage.
3. Every artifact is traceable through a complete DAG lineage in `provenance-service`, enabling bit-exact offline reproduction.
