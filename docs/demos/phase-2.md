# Phase 2 Demo Runbook: Solar Illumination and Shadow Engine

This runbook demonstrates SelenePlan's Phase 2 illumination engine, time-varying shadow ray-tracer, and interactive UI timeline scrubber.

---

## 1. Prerequisites & Services

Start the core dependencies and services:
```bash
# 1. Start Docker compose dependencies (PostgreSQL/PostGIS, Redis, Kafka, MinIO, Keycloak)
docker compose -f infra/docker-compose.yml up -d

# 2. Verify SPICE kernels are present in data/spice/
python -c "from selene_geo.spice import default_spice_manager; print('SPICE module ready')"

# 3. Launch illumination-service
uvicorn illumination_service.api.app:app --host 0.0.0.0 --port 8105 --reload

# 4. Launch web application
cd services/web && npm run dev
```

---

## 2. Automated Test Verification

Execute all unit, golden, property, and accessibility test suites:
```bash
# Run shared horizon ray-tracing golden tests
pytest libs/selene-horizon/tests/ -v

# Run illumination service golden, property, and API tests
pytest services/illumination-service/tests/ -v

# Run web UI and accessibility tests
cd services/web && npm test -- --run
```

**Expected Results:**
- `libs/selene-horizon`: 4 golden tests passed (Flat plane $0^\circ$, Conical peak $\arctan(H/D)$, Bowl crater rim angle, padding margin).
- `services/illumination-service`: 18 tests passed (bit-for-bit reproducibility, convergence $< 5\%$, property test for longest dark duration, API endpoints, authz negative test).
- `services/web`: 11 Vitest & axe-core tests passed with 0 accessibility violations.

---

## 3. Web UI Demonstration: Solar Timeline & Inspector

1. Open `http://localhost:5173` in a web browser.
2. In the top navigation bar, ensure the **Polar Map** view is selected.
3. In the **Map Layer Controls** sidebar:
   - Toggle **Solar Illumination (Time Slice)** ON.
   - Toggle **Permanent Shadow (PSR)** ON.
4. Locate the **Solar Timeline Scrubber** docked directly below the polar canvas:
   - Click **Play**: Watch the sub-solar ground track rotate around the lunar south pole. Sunlit rims glow in vibrant gold; shadowed crater interiors remain deep obsidian.
   - Adjust **Speed**: Toggle between $1\times, 2\times, 5\times, 10\times$ speeds.
   - Scrub the slider: Observe instant sub-second slice synchronization.
   - Keyboard control: Use `ArrowLeft` / `ArrowRight` or `Space` (play/pause) to step frame-by-frame.
5. Point Telemetry Inspection:
   - Hover over the **Connecting Ridge Rim** ($89.7^\circ\text{S}$): Observe `SUNLIT`, `~62% LIT` fraction, and 48-hour solar series bar chart.
   - Hover over the **Shackleton Crater Floor** ($89.9^\circ\text{S}$): Observe `PERMANENT SHADOW (PSR)`, `0% LIT`, `708h Max Dark`.
