"""HTML and Document builder using Jinja2 with strict autoescape.

Per services/report-service/SPEC.md:
- Autoescapes all variables to prevent HTML/template injection (T18).
- Unsigned plans include a visible DRAFT / NOT SIGNED watermark.
- Signed plans embed the signature, plan hash, key ID, and lineage table.
- Non-redistributable datasets are handled by omitting raw points and providing derived summary only.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, select_autoescape

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SelenePlan Mission Report: {{ plan_name }}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #1e293b; }
    .watermark { position: fixed; top: 40%; left: 10%; transform: rotate(-30deg); font-size: 64px; color: rgba(239, 68, 68, 0.2); font-weight: 900; pointer-events: none; border: 8px solid rgba(239, 68, 68, 0.2); padding: 20px 40px; }
    .header { border-bottom: 2px solid #3b82f6; padding-bottom: 12px; margin-bottom: 24px; }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }
    .badge-signed { background: #dcfce7; color: #166534; }
    .badge-draft { background: #fee2e2; color: #991b1b; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    th, td { border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }
    th { background: #f1f5f9; }
    .code-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; font-family: monospace; font-size: 13px; word-break: break-all; }
  </style>
</head>
<body>
  {% if is_draft %}
  <div class="watermark">DRAFT / NOT SIGNED</div>
  {% endif %}

  <div class="header">
    <h1>SelenePlan Mission Traverse Report</h1>
    <h2>Plan: {{ plan_name }} (Version {{ version_number }})</h2>
    <p>Project: {{ project_id }} | Generated: {{ generated_at }}</p>
    <div>
      {% if is_signed %}
      <span class="badge badge-signed">CRYPTOGRAPHICALLY SIGNED</span>
      {% else %}
      <span class="badge badge-draft">DRAFT &mdash; UNSIGNED</span>
      {% endif %}
    </div>
  </div>

  <section>
    <h3>1. Mission Summary & Metrics</h3>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Total Traverse Distance</td><td>{{ total_distance_m }} m</td></tr>
      <tr><td>Total Traverse Duration</td><td>{{ total_duration_hours }} h</td></tr>
      <tr><td>Minimum Battery Reserve</td><td>{{ min_battery_wh }} Wh</td></tr>
      <tr><td>Final Battery Reserve</td><td>{{ final_battery_wh }} Wh</td></tr>
    </table>
  </section>

  <section>
    <h3>2. Lineage & Provenance Integrity</h3>
    <table>
      <tr><th>Input Artifact</th><th>Kind</th><th>SHA-256 Checksum</th><th>Redistribution</th></tr>
      {% for item in lineage_items %}
      <tr>
        <td>{{ item.name }}</td>
        <td>{{ item.kind }}</td>
        <td><code>{{ item.sha256 }}</code></td>
        <td>{{ item.redistribution }}</td>
      </tr>
      {% endfor %}
    </table>
  </section>

  <section>
    <h3>3. Approvals & Cryptographic Signature Block</h3>
    <table>
      <tr><th>Role</th><th>Approver ID</th><th>Decision</th><th>MFA Claim</th><th>Timestamp</th></tr>
      {% for dec in decisions %}
      <tr>
        <td>Approver</td>
        <td>{{ dec.user_id }}</td>
        <td>{{ dec.decision }}</td>
        <td>{{ dec.mfa_verified }}</td>
        <td>{{ dec.timestamp }}</td>
      </tr>
      {% endfor %}
    </table>

    {% if is_signed %}
    <div class="code-box">
      <strong>Key ID:</strong> {{ signature.key_id }} (v{{ signature.key_version }})<br>
      <strong>Algorithm:</strong> {{ signature.algorithm }}<br>
      <strong>Payload Canonical SHA-256:</strong> {{ signature.payload_sha256 }}<br>
      <strong>Signature:</strong> {{ signature.signature }}<br>
      <strong>Offline Verification:</strong> <code>python tools/verify_bundle.py &lt;bundle.json&gt;</code>
    </div>
    {% else %}
    <p><em>This mission plan has not completed the two-person approval workflow and is not cryptographically signed.</em></p>
    {% endif %}
  </section>
</body>
</html>
"""

env = Environment(autoescape=select_autoescape(["html", "xml"]))
compiled_template = env.from_string(REPORT_TEMPLATE)


def render_report_html(plan_data: dict[str, Any]) -> str:
    """Render mission report HTML with autoescape and integrity safeguards."""
    is_signed = bool(plan_data.get("signature"))
    is_draft = not is_signed

    # Sanitize and handle non-redistributable datasets
    lineage_items = []
    for inp in plan_data.get("inputs", []):
        redist = inp.get("redistributable", True)
        lineage_items.append(
            {
                "name": inp.get("name", "Unknown Artifact"),
                "kind": inp.get("kind", "Data Product"),
                "sha256": inp.get("sha256", "N/A"),
                "redistribution": "Redistributable"
                if redist
                else "Derived Summary Only (Proprietary)",
            }
        )

    context = {
        "plan_name": plan_data.get("name", "Untitled Plan"),
        "version_number": plan_data.get("version_number", 1),
        "project_id": plan_data.get("project_id", "Unknown Project"),
        "generated_at": plan_data.get("generated_at", "2026-10-18T00:00:00Z"),
        "is_draft": is_draft,
        "is_signed": is_signed,
        "total_distance_m": f"{plan_data.get('total_distance_m', 0.0):.1f}",
        "total_duration_hours": f"{plan_data.get('total_duration_hours', 0.0):.2f}",
        "min_battery_wh": f"{plan_data.get('min_battery_wh', 0.0):.1f}",
        "final_battery_wh": f"{plan_data.get('final_battery_wh', 0.0):.1f}",
        "lineage_items": lineage_items,
        "decisions": plan_data.get("decisions", []),
        "signature": plan_data.get("signature"),
    }

    return compiled_template.render(**context)
