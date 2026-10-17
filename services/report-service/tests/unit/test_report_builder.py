"""Unit tests for report document builder and template security.

Per services/report-service/SPEC.md:
- AC 1: Signed plan report includes plan hash, key ID, signature, lineage.
- AC 2: Unsigned plan report includes DRAFT watermark.
- AC 3: Template and HTML injection attempts are autoescaped as plain text (T18).
- AC 5: Non-redistributable dataset handling.
"""

from report_service.templates.builder import render_report_html


def test_signed_plan_report_contains_signature_and_lineage() -> None:
    plan_data = {
        "name": "Artemis Polar Path",
        "version_number": 2,
        "project_id": "proj-shackleton",
        "total_distance_m": 420.5,
        "total_duration_hours": 1.25,
        "min_battery_wh": 380.0,
        "final_battery_wh": 415.0,
        "inputs": [
            {
                "name": "LDEM Shackleton 20m",
                "kind": "DEM",
                "sha256": "abcdef1234567890",
                "redistributable": True,
            }
        ],
        "decisions": [
            {
                "user_id": "user-app-1",
                "decision": "approve",
                "mfa_verified": True,
                "timestamp": "2026-10-18T00:00:00Z",
            },
            {
                "user_id": "user-app-2",
                "decision": "approve",
                "mfa_verified": True,
                "timestamp": "2026-10-18T00:01:00Z",
            },
        ],
        "signature": {
            "key_id": "selene-plan-signing",
            "key_version": 1,
            "algorithm": "Ed25519",
            "payload_sha256": "9988776655443322",
            "signature": "vault:v1:sig-test-bytes",
        },
    }

    html = render_report_html(plan_data)
    # AC 1: Signature block, key_id, hash, lineage
    assert "selene-plan-signing" in html
    assert "9988776655443322" in html
    assert "vault:v1:sig-test-bytes" in html
    assert "LDEM Shackleton 20m" in html
    assert "abcdef1234567890" in html
    assert "CRYPTOGRAPHICALLY SIGNED" in html
    # Watermark should NOT be present on signed report
    assert "DRAFT / NOT SIGNED" not in html


def test_unsigned_plan_contains_draft_watermark() -> None:
    plan_data = {
        "name": "Draft Traverse",
        "project_id": "proj-shackleton",
        "signature": None,
    }
    html = render_report_html(plan_data)
    # AC 2: Visible watermark present
    assert "DRAFT / NOT SIGNED" in html
    assert "DRAFT &mdash; UNSIGNED" in html


def test_html_and_template_injection_safety() -> None:
    """AC 3: Injection payloads in user-controlled fields must be escaped into harmless text."""
    evil_plan = {
        "name": "<script>alert('XSS')</script>{{ 7 * 7 }}",
        "project_id": "<img src=x onerror=alert(1)>",
        "signature": None,
    }
    html = render_report_html(evil_plan)
    # Must NOT contain raw script tag or evaluation of {{ 7 * 7 }} = 49
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;" in html
    assert "{{ 7 * 7 }}" in html or "&#123;&#123;" in html
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html


def test_non_redistributable_dataset_safeguard() -> None:
    """AC 5: Non-redistributable datasets are flagged as derived summary only."""
    plan_data = {
        "name": "Commercial Sensor Traverse",
        "project_id": "proj-shackleton",
        "inputs": [
            {
                "name": "Proprietary SAR Imagery",
                "kind": "SAR",
                "sha256": "11223344",
                "redistributable": False,
            }
        ],
    }
    html = render_report_html(plan_data)
    assert "Derived Summary Only (Proprietary)" in html
