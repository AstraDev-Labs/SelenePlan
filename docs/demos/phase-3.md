# Phase 3 Demo Runbook: Earth Visibility and Communications Line-of-Sight

This runbook demonstrates SelenePlan's Phase 3 direct-to-Earth communication line-of-sight engine, lunar libration modeling, window extraction, and UI dual timeline strip.

---

## 1. Prerequisites & Services

```bash
# 1. Start core docker compose dependencies
docker compose -f infra/docker-compose.yml up -d

# 2. Launch comms-service
uvicorn comms_service.api.app:app --host 0.0.0.0 --port 8106 --reload

# 3. Launch web application
cd services/web && npm run dev
```

---

## 2. Automated Test Verification

Execute all unit, golden, property, and API test suites:
```bash
# Run comms-service test suite
pytest services/comms-service/tests/ -v

# Run web frontend tests
cd services/web && npm test -- --run
```

**Expected Results:**
- `services/comms-service`: 19 tests passed (flat plane, ridge occultation, libration verification against direct SPICE, property tests on contiguous window extraction, REST API endpoints, authz negative test).
- `services/web`: 11 Vitest & axe-core tests passed with 0 accessibility violations.

---

## 3. Web UI Demonstration: Earth Visibility & Dual Timeline

1. Open `http://localhost:5173` in a web browser.
2. In the **Map Layer Controls** sidebar:
   - Toggle **Earth Visibility (Line of Sight)** ON.
   - Observe the polar map updating: the Shackleton rim and connecting ridge illuminate in vibrant cyan (`CONNECTED`), while the deep crater floor turns dark crimson (`BLACKOUT`).
3. Point Telemetry & Dual Timeline:
   - Hover over the **Connecting Ridge** ($89.7^\circ\text{S}$):
     - Earth Comm: `VISIBLE (+2.4° elevation)`.
     - Combined Dual Track displays both `[SUN]` (gold) and `[EARTH]` (cyan) 48-hour strips.
   - Hover over the **Shackleton Floor** ($89.9^\circ\text{S}$):
     - Earth Comm: `BLACKOUT`.
     - Identifies both Permanent Shadow (PSR) and permanent RF blackout.
4. Test API endpoint:
   - `curl -H "Authorization: Bearer mock-token-analyst-1" http://localhost:8106/v1/products/{id}/windows?x=0&y=0`
   - Returns extracted line-of-sight windows with durations in hours and blackout metrics.
