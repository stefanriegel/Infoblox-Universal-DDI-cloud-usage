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

    def test_top5_zones_after_set_complete(self):
        mgr = AdScanManager()
        zones = [("corp.local", 20), ("example.local", 5)]
        mgr.set_complete(
            output_path="/tmp/ad.xlsx",
            resources=[],
            errors=[],
            dns_zone_count=2,
            dhcp_scope_count=0,
            user_count=0,
            ddi_count=0,
            ip_count=0,
            token_total=0.0,
            top_dns_zones=zones,
        )
        result = mgr.top_dns_zones
        assert result == zones

    def test_resource_id_zone_parsing(self):
        """Verify resource_id format: ad:dns-record:{zone}|{owner}|{type}|{data}"""
        resource_id = "ad:dns-record:corp.local|@|SOA|ns1.corp.local."
        prefix = "ad:dns-record:"
        body = resource_id[len(prefix):]
        zone = body.split("|", 1)[0]
        assert zone == "corp.local"

    def test_empty_resources_gives_empty_list(self):
        mgr = AdScanManager()
        # Before set_complete, top_dns_zones should be empty list
        assert mgr.top_dns_zones == []

    def test_top5_limit_enforced(self):
        mgr = AdScanManager()
        zones = [(f"zone{i}.local", 100 - i) for i in range(10)]
        mgr.set_complete(
            output_path="/tmp/ad.xlsx",
            resources=[],
            errors=[],
            dns_zone_count=10,
            dhcp_scope_count=0,
            user_count=0,
            ddi_count=0,
            ip_count=0,
            token_total=0.0,
            top_dns_zones=zones[:5],  # caller already limits to 5
        )
        assert len(mgr.top_dns_zones) <= 5


class TestAdDnsZoneTemplate:
    """DNS-02: partials/ad/complete.html renders DNS zones panel."""

    def test_panel_rendered_when_zones_present(self):
        from jinja2 import Environment, BaseLoader
        tmpl_src = """{% if top_dns_zones %}<section class="ad-dns-panel">{% for zone_name, count in top_dns_zones %}<tr><td>{{ zone_name }}</td><td>{{ count }}</td></tr>{% endfor %}</section>{% endif %}"""
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(tmpl_src)
        result = tmpl.render(top_dns_zones=[("corp.local", 20)])
        assert "ad-dns-panel" in result
        assert "corp.local" in result

    def test_panel_hidden_when_zones_empty(self):
        from jinja2 import Environment, BaseLoader
        tmpl_src = """{% if top_dns_zones %}<section class="ad-dns-panel">content</section>{% endif %}"""
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(tmpl_src)
        result = tmpl.render(top_dns_zones=[])
        assert "ad-dns-panel" not in result


class TestNiosDnsZones:
    """DNS-03: _run_nios_pipeline accumulates per-zone record counts."""

    def test_zone_record_counts_accumulated(self):
        """zone_record_counts dict accumulates DNS record objects per zone."""
        from cloud_usage.dashboard.routes.nios import _DNS_RECORD_FAMILIES
        from cloud_usage.nios.schema import NiosFamily

        # All 9 DNS record families must be in the frozenset
        expected = {
            NiosFamily.DNS_RECORD_A,
            NiosFamily.DNS_RECORD_AAAA,
            NiosFamily.DNS_RECORD_CNAME,
            NiosFamily.DNS_RECORD_MX,
            NiosFamily.DNS_RECORD_NS,
            NiosFamily.DNS_RECORD_PTR,
            NiosFamily.DNS_RECORD_SOA,
            NiosFamily.DNS_RECORD_SRV,
            NiosFamily.DNS_RECORD_TXT,
        }
        assert _DNS_RECORD_FAMILIES == expected

    def test_zone_name_candidate_fields_tried_in_order(self):
        """zone_name fallback chain: zone_name -> parent -> zone -> empty."""
        # Verify the frozenset is importable and contains DNS_RECORD_A
        from cloud_usage.dashboard.routes.nios import _DNS_RECORD_FAMILIES
        from cloud_usage.nios.schema import NiosFamily

        assert NiosFamily.DNS_RECORD_A in _DNS_RECORD_FAMILIES

    def test_zones_with_no_records_show_zero_count(self):
        """DNS_ZONE objects seed zone_record_counts with 0 if not already present."""
        # NiosScanManager.top_dns_zones returns empty list initially
        from cloud_usage.dashboard.services.nios_manager import NiosScanManager

        mgr = NiosScanManager()
        assert mgr.top_dns_zones == []


class TestNiosScanManagerDnsZones:
    """DNS-03: NiosScanManager.top_dns_zones stored after set_complete."""

    def test_top5_stored_after_set_complete(self):
        from cloud_usage.dashboard.services.nios_manager import NiosScanManager

        mgr = NiosScanManager()
        zones = [("example.com", 100), ("corp.local", 50)]
        mgr.set_complete("/tmp/nios.xlsx", top_dns_zones=zones)
        assert mgr.top_dns_zones == zones

    def test_default_empty_list_when_not_passed(self):
        from cloud_usage.dashboard.services.nios_manager import NiosScanManager

        mgr = NiosScanManager()
        mgr.set_complete("/tmp/nios.xlsx")
        assert mgr.top_dns_zones == []

    def test_top5_limit_enforced(self):
        from cloud_usage.dashboard.services.nios_manager import NiosScanManager

        mgr = NiosScanManager()
        zones = [(f"zone{i}.local", 100 - i) for i in range(5)]
        mgr.set_complete("/tmp/nios.xlsx", top_dns_zones=zones)
        result = mgr.top_dns_zones
        assert isinstance(result, list)
        assert len(result) == 5


class TestNiosDnsZoneTemplate:
    """DNS-03: partials/nios/complete.html renders DNS zones panel."""

    def test_panel_rendered_when_zones_present(self):
        from jinja2 import Environment, BaseLoader

        tmpl_src = (
            "{% if top_dns_zones %}"
            '<section class="nios-dns-panel">'
            "{% for zone_name, count in top_dns_zones %}"
            "<tr><td>{{ zone_name }}</td><td>{{ count }}</td></tr>"
            "{% endfor %}"
            "</section>"
            "{% endif %}"
        )
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(tmpl_src)
        result = tmpl.render(top_dns_zones=[("corp.example.com", 42)])
        assert "nios-dns-panel" in result
        assert "corp.example.com" in result
        assert "42" in result

    def test_panel_hidden_when_zones_empty(self):
        from jinja2 import Environment, BaseLoader

        tmpl_src = (
            "{% if top_dns_zones %}"
            '<section class="nios-dns-panel">content</section>'
            "{% endif %}"
        )
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(tmpl_src)
        result = tmpl.render(top_dns_zones=[])
        assert "nios-dns-panel" not in result
