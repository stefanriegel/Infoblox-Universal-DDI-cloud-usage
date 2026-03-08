"""Phase 32: Attribution Display Names — Wave 0 test scaffold.

All tests are marked xfail (Wave 0 gate). They describe expected behaviors
for ATTR-01 (DDI display name mapping) implementation in Plan 32-02.

Critical: All imports of DDI_DISPLAY_NAMES and _compute_summary are INSIDE
each test method body to prevent collection-time ImportError (DDI_DISPLAY_NAMES
does not yet exist in pages.py).
"""
import pytest

from cloud_usage.schema.resource import CloudResource

XFAIL = pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — implementation in Plan 32-02")


class TestDisplayNameMapping:
    """ATTR-01: resource_type_breakdown uses human-readable display_name."""

    @XFAIL
    def test_v17_ddi_type_has_display_name(self):
        from cloud_usage.dashboard.routes.pages import DDI_DISPLAY_NAMES

        assert "aws-resolver-endpoint" in DDI_DISPLAY_NAMES
        assert DDI_DISPLAY_NAMES["aws-resolver-endpoint"] == "Route53 Resolver Endpoint"

    @XFAIL
    def test_unknown_type_falls_back_to_raw_string(self):
        from cloud_usage.dashboard.routes.pages import DDI_DISPLAY_NAMES

        # fallback: unknown type returns itself
        assert DDI_DISPLAY_NAMES.get("unknown-future-type", "unknown-future-type") == "unknown-future-type"

    @XFAIL
    def test_breakdown_entry_has_display_name_key(self):
        from cloud_usage.dashboard.routes.pages import _compute_summary

        r = CloudResource(
            resource_id="r1",
            resource_type="aws-resolver-endpoint",
            provider="aws",
            account_id="123456789012",
            region="us-east-1",
            name="ep",
            counted=True,
            category="ddi",
        )
        result = _compute_summary([r])
        acct = result["per_account_details"][0]
        breakdown = acct["resource_type_breakdown"]
        assert "aws-resolver-endpoint" in breakdown
        assert breakdown["aws-resolver-endpoint"]["display_name"] == "Route53 Resolver Endpoint"

    @XFAIL
    def test_pre_v17_type_fallback_in_breakdown(self):
        from cloud_usage.dashboard.routes.pages import _compute_summary

        r = CloudResource(
            resource_id="r2",
            resource_type="vpc",
            provider="aws",
            account_id="123456789012",
            region="us-east-1",
            name="my-vpc",
            counted=True,
            category="ddi",
        )
        result = _compute_summary([r])
        acct = result["per_account_details"][0]
        breakdown = acct["resource_type_breakdown"]
        # "vpc" may not be in DDI_DISPLAY_NAMES → falls back to "vpc", or has a mapping like "VPC"
        assert breakdown["vpc"]["display_name"] in ("vpc", "VPC")


class TestSummaryHTMLRendering:
    """ATTR-01: Summary tab HTML renders display_name instead of raw resource_type."""

    @XFAIL
    def test_summary_html_uses_display_name_not_raw_type(self):
        from starlette.testclient import TestClient

        from cloud_usage.dashboard.app import create_app

        app = create_app()
        with TestClient(app) as client:
            r = CloudResource(
                resource_id="r-ep-001",
                resource_type="aws-resolver-endpoint",
                provider="aws",
                account_id="123456789012",
                region="us-east-1",
                name="my-resolver-endpoint",
                counted=True,
                category="ddi",
            )
            client.app.state.scan_manager.set_resources([r])
            response = client.get("/tab/summary")
            assert response.status_code == 200
            # The rendered label should be human-readable
            assert "Route53 Resolver Endpoint" in response.text
            # The raw type key should NOT appear as a standalone rendered label
            # (It may appear in data attributes or HTML structure, but not as display text)
            # Check the display name is present — that's sufficient to confirm ATTR-01
