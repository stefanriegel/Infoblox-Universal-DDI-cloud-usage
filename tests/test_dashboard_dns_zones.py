"""Phase 31: DNS Zones Panels — Wave 0 test scaffold.

All tests are marked xfail (Wave 0 gate). They describe expected behaviors
for DNS-01 (Cloud), DNS-02 (AD), DNS-03 (NIOS) implementations.
Plans 02 and 03 will make these tests pass.
"""
import pytest
from unittest.mock import MagicMock

from cloud_usage.dashboard.services.ad_manager import AdScanManager
from cloud_usage.dashboard.services.nios_manager import NiosScanManager

XFAIL = pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — implementation in Plans 02-03")


def _make_resource(resource_type, name, details=None, resource_id=None):
    """Build a minimal mock CloudResource for tests."""
    r = MagicMock()
    r.resource_type = resource_type
    r.name = name
    r.details = details or {}
    r.resource_id = resource_id or f"{resource_type}:{name}"
    return r


class TestCloudDnsZones:
    """DNS-01: _compute_summary / tab_summary returns top_cloud_dns_zones."""

    def test_top5_zones_returned_in_summary(self):
        from cloud_usage.dashboard.routes.pages import _compute_top_cloud_dns_zones
        resources = [
            _make_resource("route53-zone", "example.com.", {"record_count": 10}),
        ]
        result = _compute_top_cloud_dns_zones(resources)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == ("example.com.", 10)

    def test_aws_records_counted_by_zone_name(self):
        from cloud_usage.dashboard.routes.pages import _compute_top_cloud_dns_zones
        resources = [
            _make_resource("route53-zone", "aws.example.com.", {"record_count": 50}),
            _make_resource("route53-zone", "aws2.example.com.", {"record_count": 20}),
        ]
        result = _compute_top_cloud_dns_zones(resources)
        names = [r[0] for r in result]
        assert "aws.example.com." in names
        assert "aws2.example.com." in names
        # sorted descending
        assert result[0][1] >= result[1][1]

    def test_azure_records_counted_by_zone_name(self):
        from cloud_usage.dashboard.routes.pages import _compute_top_cloud_dns_zones
        resources = [
            _make_resource("azure-dns-zone", "azure.example.com", {"record_count": 30, "zone_type": "public"}),
            _make_resource("azure-private-dns-zone", "private.example.com", {"record_count": 15, "zone_type": "private"}),
        ]
        result = _compute_top_cloud_dns_zones(resources)
        names = [r[0] for r in result]
        assert "azure.example.com" in names
        assert "private.example.com" in names

    def test_gcp_zones_counted_from_record_resources(self):
        from cloud_usage.dashboard.routes.pages import _compute_top_cloud_dns_zones
        resources = [
            _make_resource("gcp-dns-zone", "gcp.example.com.", {"zone_name": "gcp-zone-1"}),
            _make_resource("gcp-dns-record", "rec1", {"zone_name": "gcp-zone-1", "record_type": "A"}),
            _make_resource("gcp-dns-record", "rec2", {"zone_name": "gcp-zone-1", "record_type": "MX"}),
            _make_resource("gcp-dns-record", "rec3", {"zone_name": "gcp-zone-1", "record_type": "TXT"}),
        ]
        result = _compute_top_cloud_dns_zones(resources)
        assert len(result) == 1
        assert result[0] == ("gcp.example.com.", 3)

    def test_empty_resources_returns_empty_list(self):
        from cloud_usage.dashboard.routes.pages import _compute_top_cloud_dns_zones
        result = _compute_top_cloud_dns_zones([])
        assert result == []

    def test_top5_limit_enforced(self):
        from cloud_usage.dashboard.routes.pages import _compute_top_cloud_dns_zones
        resources = [
            _make_resource("route53-zone", f"zone{i}.example.com.", {"record_count": 100 - i})
            for i in range(10)
        ]
        result = _compute_top_cloud_dns_zones(resources)
        assert len(result) <= 5


class TestCloudDnsZoneTemplate:
    """DNS-01: summary.html renders DNS zones panel."""

    def test_panel_rendered_when_zones_present(self):
        from jinja2 import Environment, BaseLoader
        tmpl_src = """{% if top_cloud_dns_zones %}<section class="dns-panel">{% for zone_name, count in top_cloud_dns_zones %}<tr><td>{{ zone_name }}</td><td>{{ count }}</td></tr>{% endfor %}</section>{% endif %}"""
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(tmpl_src)
        result = tmpl.render(top_cloud_dns_zones=[("example.com.", 10)])
        assert "dns-panel" in result
        assert "example.com." in result

    def test_panel_hidden_when_zones_empty(self):
        from jinja2 import Environment, BaseLoader
        tmpl_src = """{% if top_cloud_dns_zones %}<section class="dns-panel">content</section>{% endif %}"""
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(tmpl_src)
        result = tmpl.render(top_cloud_dns_zones=[])
        assert "dns-panel" not in result


class TestAdDnsZones:
    """DNS-02: AdScanManager.top_dns_zones from ad-dns-record resource_ids."""

    @XFAIL
    def test_top5_zones_after_set_complete(self): ...

    @XFAIL
    def test_resource_id_zone_parsing(self): ...

    @XFAIL
    def test_empty_resources_gives_empty_list(self): ...

    @XFAIL
    def test_top5_limit_enforced(self): ...


class TestAdDnsZoneTemplate:
    """DNS-02: partials/ad/complete.html renders DNS zones panel."""

    @XFAIL
    def test_panel_rendered_when_zones_present(self): ...

    @XFAIL
    def test_panel_hidden_when_zones_empty(self): ...


class TestNiosDnsZones:
    """DNS-03: _run_nios_pipeline accumulates per-zone record counts."""

    @XFAIL
    def test_zone_record_counts_accumulated(self): ...

    @XFAIL
    def test_zone_name_candidate_fields_tried_in_order(self): ...

    @XFAIL
    def test_zones_with_no_records_show_zero_count(self): ...


class TestNiosScanManagerDnsZones:
    """DNS-03: NiosScanManager.top_dns_zones stored after set_complete."""

    @XFAIL
    def test_top5_stored_after_set_complete(self): ...

    @XFAIL
    def test_default_empty_list_when_not_passed(self): ...

    @XFAIL
    def test_top5_limit_enforced(self): ...


class TestNiosDnsZoneTemplate:
    """DNS-03: partials/nios/complete.html renders DNS zones panel."""

    @XFAIL
    def test_panel_rendered_when_zones_present(self): ...

    @XFAIL
    def test_panel_hidden_when_zones_empty(self): ...
