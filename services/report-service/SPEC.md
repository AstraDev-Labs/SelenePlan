# SPEC: report-service

**Port:** 8108 | **Tech:** FastAPI, WeasyPrint (HTML to PDF), Jinja2 (autoescape on), Matplotlib or server-side map rendering | **Phase:** 5

## Purpose
Generate mission reports and exports (FR-33): PDF report, GeoJSON, CSV waypoints. Each report embeds the signature, plan hash, key ID, and lineage so a printed or shared copy can be checked.

## Responsibilities
1. Build a PDF with: summary, AOI map, hazard/illumination/visibility context at key times, site ranking table with score breakdown, route map, energy and sun/comms timeline plots, explanations, assumptions and limitations (from `docs/08-science-notes.md`), lineage table (dataset versions, code versions, model versions), approvals, and signature block with the verification instructions.
2. Export GeoJSON of the route and CSV of waypoints; each export includes the plan hash and signature reference.
3. Store reports in object storage; record SHA-256; emit `report.completed`.
4. Unsigned plans may produce a report with a visible **DRAFT / NOT SIGNED** watermark.

## Security
- Templates auto-escape; no user-provided HTML or raw template strings (T18).
- No network access during rendering; fonts and images local.
- Reports for a project are only visible to its members (T2).
- Never include secrets or internal URLs.
- Dataset license/redistribution flags are checked; if a dataset is not redistributable, omit raw data from the bundle and include only derived summaries.

## API
`POST /v1/reports` (202), `GET /v1/reports/{id}`, `GET /v1/reports/{id}/download`.

## Events
Consumes `report.requested`, `plan.signed`. Produces `report.completed`, `audit.event`.

## Acceptance criteria
1. Report for a signed plan contains the correct plan hash, key ID, signature, and lineage; an automated test parses the PDF text and compares to the DB.
2. Report for an unsigned plan has the watermark.
3. Template injection and HTML injection attempts in plan names and comments are rendered as plain text.
4. Rendering finishes within a documented time for a typical plan.
5. Non-redistributable dataset handling test passes.
6. Another project's member cannot download the report.

## Folder layout
```
services/report-service/
  src/report_service/{api,worker,templates,plots,exports,events}/
  tests/{unit,component,security}/
```
