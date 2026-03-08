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


class TestCloudDnsZones:
    """DNS-01: _compute_summary / tab_summary returns top_cloud_dns_zones."""

    @XFAIL
    def test_top5_zones_returned_in_summary(self): ...

    @XFAIL
    def test_aws_records_counted_by_zone_name(self): ...

    @XFAIL
    def test_azure_records_counted_by_zone_name(self): ...

    @XFAIL
    def test_gcp_zones_counted_from_record_resources(self): ...

    @XFAIL
    def test_empty_resources_returns_empty_list(self): ...

    @XFAIL
    def test_top5_limit_enforced(self): ...


class TestCloudDnsZoneTemplate:
    """DNS-01: summary.html renders DNS zones panel."""

    @XFAIL
    def test_panel_rendered_when_zones_present(self): ...

    @XFAIL
    def test_panel_hidden_when_zones_empty(self): ...


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
