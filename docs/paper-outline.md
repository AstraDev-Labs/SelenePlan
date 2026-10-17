# Academic Paper Outline: SelenePlan

**Working Title:** *SelenePlan: A Cryptographically Verifiable, Joint Space-Time Co-Optimization Framework for Lunar South Pole Traverse Planning and Mission Assurance*

---

## 1. Abstract
- **Context:** The lunar south pole presents extreme operational challenges: low-grazing solar illumination with moving shadows, complex topographic crater slopes, intermittent direct-to-Earth communication visibility due to lunar libration, and strict rover energy margins.
- **Problem:** Existing mission planning systems isolate terrain, illumination, power, and comms analyses into sequential silos, lacking real-time joint co-optimization, contrastive explainability, and cryptographic non-repudiation against data poisoning and plan tampering.
- **Contribution:** We present SelenePlan, an event-driven microservice platform that integrates:
  1. A high-performance azimuthal horizon-profile illumination and Earth line-of-sight raytracing engine driven by SPICE ephemerides and LOLA DEMs.
  2. A time-expanded A* graph search that jointly co-optimizes rover kinematic paths, battery state-of-charge dynamics, solar power collection, and comms windows.
  3. A contrastive explainability layer that generates structured natural-language rejection rationales for candidate routes.
  4. A zero-trust mission integrity boundary incorporating four-eyes OPA policy enforcement, RFC 8785 Ed25519 digital signatures, and a tamper-evident SHA-256 hash-chained audit log.
- **Results:** Validation against synthetic golden crater benchmarks and real Shackleton Crater south-polar topography ($89.9^\circ\text{ S}$) demonstrates $100\%$ feasible traverse synthesis in $< 500\text{ ms}$, zero battery depletion violations, instant detection of single-byte plan tampering, and bit-exact deterministic replay.

---

## 2. Introduction & Related Work
- **The Lunar South Polar Environment:** Topographic relief, permanently shadowed regions (PSRs), volatile cold traps, and low Sun elevation ($< 1.5^\circ$).
- **Limitations of Current Planetary Mission Planners:**
  - Overview of NASA VIPER, Mars 2020 onboard/ground planners, and conventional planetary GIS plugins.
  - The disconnection between ground path planners and power/thermal simulation tools.
  - The lack of formal explainability for flight director review boards.
- **Security & Integrity in Autonomous Space Missions:**
  - Supply-chain risks in planetary DEMs, AI/ML crater detection models, and ground station data pipelines.
  - The need for cryptographic non-repudiation in multi-agency exploration (Artemis Accords).

---

## 3. System Architecture
- **Microservices Topology:** Separation of concerns across Core Gateway, Analysis Engines, Planning & Governance, and Storage tiers.
- **Asynchronous Event-Driven Pipeline:** Kafka message bus orchestration with join barriers and dead-letter queue (DLQ) isolation.
- **Lunar Cartographic Foundation:** Native IAU 2000 Moon reference sphere ($R = 1,737,400\text{ m}$) preventing flat-Earth and WGS84 distortion artifacts.

---

## 4. Algorithms & Mathematical Formulation
- **Horizon-Mask Illumination & Earth Visibility:**
  - Azimuthal discretization (360/720 bins), radial elevation profiling, and SPICE ephemerides projection.
- **Rover Energy & Kinematic Dynamics:**
  - Formulation of drive power $P_{drive}(\alpha, v) = m \cdot g \cdot v \cdot (\sin\alpha + \mu\cos\alpha) + P_{base}$.
  - Solar generation $P_{solar}(t) = \eta \cdot A_{panel} \cdot S_0 \cdot \max(0, \cos\theta_{inc}(t)) \cdot \mathbb{I}_{lit}(x, y, t)$.
  - Battery state-of-charge continuity: $E(t + \Delta t) = E(t) + (P_{solar} - P_{drive} - P_{idle}) \cdot \Delta t$.
- **Time-Expanded Space-Time A* Search:**
  - State space $\mathcal{S} = (x, y, t)$, action space $\mathcal{A} = \{\text{drive}, \text{charge}, \text{idle}\}$.
  - Admissible heuristic $h(s) = \frac{d(x, y, x_{goal}, y_{goal})}{v_{max}} \cdot c_{time} + E_{min\_drive}$.
- **Contrastive Rejection Explainer:**
  - Evaluation of counterfactual paths and formal mapping to rule constraint violations.

---

## 5. Security & Mission Governance Model
- **Four-Eyes Policy Formulation:** Rego policy specification requiring $N=2$ distinct approvers with verified MFA claims; strict prohibition of self-approval by creators.
- **RFC 8785 Canonical JSON & Ed25519 Signing:** Byte-exact serialization, cryptographic hash verification, and key version rotation via Vault Transit.
- **Tamper-Evident SHA-256 Audit Chain:** Continuous hash chaining $\text{hash}_n = \mathcal{H}(\text{hash}_{n-1} \,\|\, m_n)$ with daily S3 Object Lock anchoring.

---

## 6. Experimental Validation & Results
- **Golden Benchmark Tests:** Analytic cones, inclined planes, and synthetic crater geometries verifying horizon raytracing and slope invariance under coordinate rotations.
- **Real Lunar Data Execution:** Performance and scientific validation over Shackleton Crater ($20\text{ km} \times 20\text{ km}$, 20m/px LOLA DEM).
- **Soak & Scalability Benchmarks:** Sub-500ms p95 latency under concurrent loads; zero memory growth over 48 hours.
- **Security & Penetration Test Outcomes:** Verification of ASVS v4.0 compliance, zero open High/Critical vulnerabilities, and verified tamper rejection.

---

## 7. Limitations & Future Work
- Point-source solar assumption vs finite solar disk penumbra.
- Unmodeled terramechanics (wheel slippage, regolith sinkage, and thermal dissipation).
- Future integration of relay satellite constellations (e.g. Lunar Pathfinder) beyond direct-to-Earth LOS.

---

## 8. Ethics, Open Science & Reproducibility Statement
- Commitment to open scientific reproducibility; public data sourcing (NASA PDS, LOLA); open-source release of core tools; offline verification and replay tooling.
