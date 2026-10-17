# report-service

**Port:** 8108 | **Tech:** FastAPI, Jinja2, GeoJSON, CSV | **Phase:** 5

## Purpose
Generates tamper-evident, publication-quality mission reports in HTML/PDF and structured formats, embedding cryptographic signatures, waypoints, and full product lineage (FR-33).

## Implemented Features
1. **Document Builder:** Autoescaping Jinja2 templates preventing HTML and template injection attacks (T18).
2. **Draft Watermark:** Prominent `DRAFT / NOT SIGNED` watermark rendered for unsigned plan reports.
3. **Cryptographic Signature Block:** Embeds plan SHA-256 digest, key ID, signature string, and offline verification instructions on approved/signed plans.
4. **GeoJSON & CSV Waypoint Exports:** Embeds plan hash and signature metadata headers in structured waypoint exports.
5. **Dataset Licensing Safeguards:** Omits raw points and provides derived summaries for non-redistributable proprietary datasets.

## Local Development & Testing
```bash
pytest services/report-service/tests/ -v
```
