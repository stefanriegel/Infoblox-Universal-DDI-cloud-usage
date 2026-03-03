"""
Tests for Phase 15 NIOS dashboard integration.

Covers all 5 Phase 15 success criteria:
  SC-1: GET /tab/nios navigable — returns 200 HTML with NIOS content
  SC-2: POST /nios/upload returns member list (hostname, virtual_oid, lease_count)
  SC-3: POST /nios/run dispatches pipeline; GET /download/{xlsx} serves result
  SC-4: File saved to disk before background thread; re-upload resets state
  SC-5: nios_manager and scan_manager are independent objects; separate EventBridge instances

Also covers NiosScanManager state machine unit tests.
"""

from __future__ import annotations

import io
import os
import sys
import tarfile
import tempfile
import threading
from pathlib import Path
from unittest import mock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from cloud_usage.dashboard.app import create_app
from cloud_usage.dashboard.services.nios_manager import NiosState, NiosScanManager
from cloud_usage.dashboard.services.scan_manager import ScanState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_tar_gz() -> bytes:
    """Create a minimal valid .tar.gz with a stub onedb.xml inside.

    Returns:
        Bytes of a valid .tar.gz archive containing onedb.xml.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        xml_content = b'<?xml version="1.0"?><NIOS_Grid version="8.6.0"></NIOS_Grid>'
        info = tarfile.TarInfo(name="onedb.xml")
        info.size = len(xml_content)
        tf.addfile(info, io.BytesIO(xml_content))
    return buf.getvalue()


_FAKE_MEMBERS = [
    {"virtual_oid": "oid-001", "hostname": "grid-master.example.com", "lease_count": 150},
    {"virtual_oid": "oid-002", "hostname": "member-01.example.com", "lease_count": 75},
]


# ---------------------------------------------------------------------------
# NiosScanManager unit tests
# ---------------------------------------------------------------------------


class TestNiosScanManager:
    """Unit tests for the NiosScanManager state machine."""

    def test_initial_state_is_idle(self) -> None:
        """NiosScanManager starts in IDLE state with no stored data."""
        m = NiosScanManager()
        assert m.state == NiosState.IDLE
        assert m.upload_path is None
        assert m.original_filename is None
        assert m.output_path is None
        assert m.error is None
        assert m.scenario_suite is None

    def test_set_upload_stores_path_and_filename(self) -> None:
        """set_upload() stores path and original_filename."""
        m = NiosScanManager()
        m.set_upload("/tmp/backup.tar.gz", "backup.tar.gz")
        assert m.upload_path == "/tmp/backup.tar.gz"
        assert m.original_filename == "backup.tar.gz"

    def test_start_transitions_to_running(self) -> None:
        """start() transitions IDLE -> RUNNING."""
        m = NiosScanManager()
        m.start()
        assert m.state == NiosState.RUNNING

    def test_can_start_false_when_running(self) -> None:
        """can_start() returns False when state is RUNNING."""
        m = NiosScanManager()
        m.start()
        assert m.can_start() is False

    def test_can_start_true_when_idle(self) -> None:
        """can_start() returns True when state is IDLE."""
        m = NiosScanManager()
        assert m.can_start() is True

    def test_set_complete_transitions_to_complete(self) -> None:
        """set_complete() transitions RUNNING -> COMPLETE and stores output_path."""
        m = NiosScanManager()
        m.start()
        m.set_complete("/tmp/out.xlsx", scenario_suite=None)
        assert m.state == NiosState.COMPLETE
        assert m.output_path == "/tmp/out.xlsx"

    def test_set_error_transitions_to_error(self) -> None:
        """set_error() transitions RUNNING -> ERROR and stores message."""
        m = NiosScanManager()
        m.start()
        m.set_error("parse failed")
        assert m.state == NiosState.ERROR
        assert m.error == "parse failed"

    def test_reset_clears_analysis_state(self) -> None:
        """reset() returns to IDLE and clears output_path, error, scenario_suite."""
        m = NiosScanManager()
        m.set_upload("/tmp/backup.tar.gz", "backup.tar.gz")
        m.start()
        m.set_complete("/tmp/out.xlsx")
        m.reset()
        assert m.state == NiosState.IDLE
        assert m.output_path is None
        assert m.error is None
        assert m.scenario_suite is None
        # upload_path and original_filename survive reset (used for re-run display)
        assert m.upload_path == "/tmp/backup.tar.gz"
        assert m.original_filename == "backup.tar.gz"

    def test_double_start_raises_runtime_error(self) -> None:
        """start() raises RuntimeError if already RUNNING."""
        m = NiosScanManager()
        m.start()
        with pytest.raises(RuntimeError, match="already running"):
            m.start()

    def test_scenario_suite_stored_on_complete(self) -> None:
        """set_complete() with scenario_suite stores it for summary card display."""
        m = NiosScanManager()
        m.start()
        fake_suite = object()
        m.set_complete("/tmp/out.xlsx", scenario_suite=fake_suite)
        assert m.scenario_suite is fake_suite

    def test_thread_safety_concurrent_start_raises(self) -> None:
        """Only one start() wins when called concurrently from multiple threads."""
        m = NiosScanManager()
        errors = []

        def try_start():
            try:
                m.start()
            except RuntimeError:
                errors.append(True)

        threads = [threading.Thread(target=try_start) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one start should succeed, the rest should raise
        assert m.state == NiosState.RUNNING
        assert len(errors) == 4


# ---------------------------------------------------------------------------
# SC-5: State independence
# ---------------------------------------------------------------------------


class TestStateIndependence:
    """SC-5: nios_manager and scan_manager are fully independent objects."""

    def test_nios_manager_is_not_scan_manager(self) -> None:
        """app.state.nios_manager and app.state.scan_manager are different objects."""
        app = create_app()
        with TestClient(app) as client:
            assert client.app.state.nios_manager is not client.app.state.scan_manager

    def test_nios_event_bridge_is_not_cloud_event_bridge(self) -> None:
        """app.state.nios_event_bridge and app.state.event_bridge are different instances."""
        app = create_app()
        with TestClient(app) as client:
            assert client.app.state.nios_event_bridge is not client.app.state.event_bridge

    def test_nios_running_does_not_affect_scan_manager(self) -> None:
        """Setting nios_manager to RUNNING leaves scan_manager in IDLE."""
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/x.tar.gz", "x.tar.gz")
            client.app.state.nios_manager.start()
            assert client.app.state.nios_manager.state == NiosState.RUNNING
            assert client.app.state.scan_manager.state == ScanState.IDLE


# ---------------------------------------------------------------------------
# SC-1: Tab navigable
# ---------------------------------------------------------------------------


class TestNiosTab:
    """SC-1: GET /tab/nios is navigable and returns NIOS content."""

    def test_tab_nios_returns_200(self) -> None:
        """GET /tab/nios returns HTTP 200."""
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/tab/nios")
            assert r.status_code == 200

    def test_tab_nios_returns_html(self) -> None:
        """GET /tab/nios returns text/html content type."""
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/tab/nios")
            assert "text/html" in r.headers["content-type"]

    def test_tab_nios_contains_nios_text(self) -> None:
        """GET /tab/nios response contains 'NIOS' in body."""
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/tab/nios")
            assert "NIOS" in r.text

    def test_tab_nios_contains_tab_bar_link(self) -> None:
        """GET /tab/nios response includes the NIOS tab link in the tab bar."""
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/tab/nios")
            assert "/tab/nios" in r.text

    def test_tab_nios_does_not_modify_scan_manager_state(self) -> None:
        """Navigating to /tab/nios does not change cloud scan state (SC-5)."""
        app = create_app()
        with TestClient(app) as client:
            client.get("/tab/nios")
            assert client.app.state.scan_manager.state == ScanState.IDLE

    def test_tab_bar_has_four_tabs(self) -> None:
        """GET /tab/nios response tab bar contains links for all 4 tabs."""
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/tab/nios")
            assert "/tab/progress" in r.text
            assert "/tab/results" in r.text
            assert "/tab/summary" in r.text
            assert "/tab/nios" in r.text


# ---------------------------------------------------------------------------
# SC-4: File saved to disk
# ---------------------------------------------------------------------------


class TestFileUpload:
    """SC-4: POST /nios/upload saves file to disk before returning."""

    def test_upload_saves_file_to_output_dir(self) -> None:
        """POST /nios/upload saves .tar.gz to output/nios_upload_*.tar.gz."""
        app = create_app()
        tar_gz_bytes = _make_minimal_tar_gz()

        saved_paths = []

        def fake_get_member_counts(path: str) -> list:
            saved_paths.append(path)
            return _FAKE_MEMBERS

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._get_member_counts_sync",
            side_effect=fake_get_member_counts,
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/nios/upload",
                    files={"file": ("mybackup.tar.gz", tar_gz_bytes, "application/gzip")},
                )
                assert r.status_code == 200

        assert len(saved_paths) == 1
        saved_path = saved_paths[0]
        assert saved_path.startswith("output/nios_upload_")
        assert saved_path.endswith(".tar.gz")
        assert os.path.exists(saved_path), f"File not found: {saved_path}"

        # Cleanup
        if os.path.exists(saved_path):
            os.remove(saved_path)

    def test_upload_stores_original_filename(self) -> None:
        """POST /nios/upload stores the original filename in nios_manager."""
        app = create_app()
        tar_gz_bytes = _make_minimal_tar_gz()

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._get_member_counts_sync",
            return_value=_FAKE_MEMBERS,
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/nios/upload",
                    files={"file": ("grid_backup_2026.tar.gz", tar_gz_bytes, "application/gzip")},
                )
                assert r.status_code == 200
                assert client.app.state.nios_manager.original_filename == "grid_backup_2026.tar.gz"

            saved_path = client.app.state.nios_manager.upload_path
            if saved_path and os.path.exists(saved_path):
                os.remove(saved_path)

    def test_reupload_resets_nios_state_to_idle(self) -> None:
        """Re-uploading resets NIOS state to IDLE (prior analysis results cleared)."""
        app = create_app()
        tar_gz_bytes = _make_minimal_tar_gz()

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._get_member_counts_sync",
            return_value=_FAKE_MEMBERS,
        ):
            with TestClient(app) as client:
                # Simulate a completed analysis
                client.app.state.nios_manager.set_upload("/tmp/old.tar.gz", "old.tar.gz")
                client.app.state.nios_manager.start()
                client.app.state.nios_manager.set_complete("/tmp/old.xlsx")
                assert client.app.state.nios_manager.state == NiosState.COMPLETE

                # Re-upload should reset to IDLE
                r = client.post(
                    "/nios/upload",
                    files={"file": ("new_backup.tar.gz", tar_gz_bytes, "application/gzip")},
                )
                assert r.status_code == 200
                assert client.app.state.nios_manager.state == NiosState.IDLE
                assert client.app.state.nios_manager.output_path is None

            saved_path = client.app.state.nios_manager.upload_path
            if saved_path and os.path.exists(saved_path):
                os.remove(saved_path)


# ---------------------------------------------------------------------------
# SC-2: Member list
# ---------------------------------------------------------------------------


class TestMemberList:
    """SC-2: POST /nios/upload returns member list with hostname, virtual_oid, lease_count."""

    def test_upload_response_contains_member_hostname(self) -> None:
        """POST /nios/upload HTML response contains member hostnames."""
        app = create_app()
        tar_gz_bytes = _make_minimal_tar_gz()

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._get_member_counts_sync",
            return_value=_FAKE_MEMBERS,
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/nios/upload",
                    files={"file": ("backup.tar.gz", tar_gz_bytes, "application/gzip")},
                )
                assert r.status_code == 200
                assert "grid-master.example.com" in r.text
                assert "member-01.example.com" in r.text

            saved_path = client.app.state.nios_manager.upload_path
            if saved_path and os.path.exists(saved_path):
                os.remove(saved_path)

    def test_upload_response_contains_virtual_oid(self) -> None:
        """POST /nios/upload HTML response contains virtual_oid values.

        Note (PERF-01): lease_count column removed from the upload step. Lease counts
        are deferred to the analysis run result. The template now shows only
        Hostname, Virtual OID, and Assign NIOSX columns.
        """
        app = create_app()
        tar_gz_bytes = _make_minimal_tar_gz()

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._get_member_counts_sync",
            return_value=_FAKE_MEMBERS,
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/nios/upload",
                    files={"file": ("backup.tar.gz", tar_gz_bytes, "application/gzip")},
                )
                assert r.status_code == 200
                assert "oid-001" in r.text
                # lease_count column no longer rendered at upload time (PERF-01)
                assert "DHCP Leases" not in r.text

            saved_path = client.app.state.nios_manager.upload_path
            if saved_path and os.path.exists(saved_path):
                os.remove(saved_path)

    def test_upload_response_has_niosx_checkboxes(self) -> None:
        """POST /nios/upload HTML response has checkbox inputs with name='niosx_member'."""
        app = create_app()
        tar_gz_bytes = _make_minimal_tar_gz()

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._get_member_counts_sync",
            return_value=_FAKE_MEMBERS,
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/nios/upload",
                    files={"file": ("backup.tar.gz", tar_gz_bytes, "application/gzip")},
                )
                assert r.status_code == 200
                assert 'name="niosx_member"' in r.text

            saved_path = client.app.state.nios_manager.upload_path
            if saved_path and os.path.exists(saved_path):
                os.remove(saved_path)


# ---------------------------------------------------------------------------
# SC-3: Run and download
# ---------------------------------------------------------------------------


class TestRunAndDownload:
    """SC-3: POST /nios/run transitions state; GET /download/{xlsx} serves file."""

    def test_run_without_upload_returns_400(self) -> None:
        """POST /nios/run without prior upload returns 400."""
        app = create_app()
        with TestClient(app) as client:
            r = client.post("/nios/run", data={})
            assert r.status_code == 400

    def test_run_transitions_state_to_running(self) -> None:
        """POST /nios/run transitions nios_manager state to RUNNING."""
        app = create_app()

        with mock.patch(
            "cloud_usage.dashboard.routes.nios._run_nios_pipeline",
        ) as mock_pipeline:
            with TestClient(app) as client:
                # Set up a pre-uploaded backup
                client.app.state.nios_manager.set_upload(
                    "/tmp/fake_backup.tar.gz", "fake_backup.tar.gz"
                )

                r = client.post("/nios/run", data={})
                assert r.status_code == 200
                # State should be RUNNING (pipeline runs in background thread)
                assert client.app.state.nios_manager.state == NiosState.RUNNING

    def test_run_returns_step2_html(self) -> None:
        """POST /nios/run returns HTML containing running state content."""
        app = create_app()

        with mock.patch("cloud_usage.dashboard.routes.nios._run_nios_pipeline"):
            with TestClient(app) as client:
                client.app.state.nios_manager.set_upload(
                    "/tmp/fake_backup.tar.gz", "fake_backup.tar.gz"
                )
                r = client.post("/nios/run", data={})
                assert r.status_code == 200
                assert "text/html" in r.headers["content-type"]
                # step2_run.html contains running state content
                assert "Run Analysis" in r.text or "nios-progress-area" in r.text

    def test_run_while_already_running_returns_409(self) -> None:
        """POST /nios/run while analysis is already RUNNING returns 409."""
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload(
                "/tmp/fake_backup.tar.gz", "fake_backup.tar.gz"
            )
            client.app.state.nios_manager.start()
            r = client.post("/nios/run", data={})
            assert r.status_code == 409

    def test_download_existing_xlsx_returns_200(self) -> None:
        """GET /download/{filename} returns 200 for an existing xlsx file."""
        os.makedirs("output", exist_ok=True)
        # Create a real temp xlsx in output/
        with tempfile.NamedTemporaryFile(
            dir="output", suffix=".xlsx", delete=False, prefix="nios_test_"
        ) as f:
            f.write(b"PK fake xlsx content")
            temp_path = f.name

        filename = os.path.basename(temp_path)
        app = create_app()
        try:
            with TestClient(app) as client:
                r = client.get(f"/download/{filename}")
                assert r.status_code == 200
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_complete_template_has_download_link(self) -> None:
        """GET /tab/nios in COMPLETE state renders download link to /download/{filename}."""
        os.makedirs("output", exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir="output", suffix=".xlsx", delete=False, prefix="nios_complete_test_"
        ) as f:
            f.write(b"PK fake xlsx")
            temp_path = f.name

        filename = os.path.basename(temp_path)
        app = create_app()
        try:
            with TestClient(app) as client:
                # Set state to COMPLETE with a real output path
                client.app.state.nios_manager.set_upload(temp_path, "backup.tar.gz")
                client.app.state.nios_manager.start()
                client.app.state.nios_manager.set_complete(temp_path)

                r = client.get("/tab/nios")
                assert r.status_code == 200
                assert f"/download/{filename}" in r.text
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ---------------------------------------------------------------------------
# Phase 19 — BRKDN-01, BRKDN-02: Scenario formula breakdown
# ---------------------------------------------------------------------------


def _make_scenario_suite_no_hybrid():
    """Build a minimal ScenarioSuite without a hybrid scenario for testing."""
    from cloud_usage.nios.scenarios import (
        MemberScenarioRow,
        ScenarioResult,
        ScenarioSuite,
    )

    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=1234,
        active_ip_count=500,
        asset_count=0,
        token_total=44.68,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=1234,
        active_ip_count=500,
        asset_count=0,
        token_total=88.08,
    )
    member_attribution = [
        MemberScenarioRow(
            member_hostname="grid-master.example.com",
            group="nios",
            ddi_count=800,
            active_ip_count=300,
            asset_count=0,
            token_contribution=28.0,
        ),
        MemberScenarioRow(
            member_hostname="member-01.example.com",
            group="nios",
            ddi_count=434,
            active_ip_count=200,
            asset_count=0,
            token_contribution=16.68,
        ),
    ]
    return ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=None,
        member_attribution=member_attribution,
        migration_split_used=None,
    )


def _make_scenario_suite_with_hybrid():
    """Build a ScenarioSuite with a hybrid scenario for testing."""
    from cloud_usage.nios.scenarios import (
        HybridScenarioResult,
        MemberScenarioRow,
        ScenarioResult,
        ScenarioSuite,
    )

    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=2000,
        active_ip_count=1000,
        asset_count=0,
        token_total=80.0,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=2000,
        active_ip_count=1000,
        asset_count=0,
        token_total=156.92,
    )
    nios_sub = ScenarioResult(
        name="nios_remaining",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=1200,
        active_ip_count=700,
        asset_count=0,
        token_total=52.0,
    )
    niosx_sub = ScenarioResult(
        name="niosx_migrated",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=800,
        active_ip_count=300,
        asset_count=0,
        token_total=55.08,
    )
    hybrid_uddi = HybridScenarioResult(
        nios_sub=nios_sub,
        niosx_sub=niosx_sub,
        combined_total=107.08,
    )
    member_attribution = [
        MemberScenarioRow(
            member_hostname="grid-master.example.com",
            group="nios",
            ddi_count=1200,
            active_ip_count=700,
            asset_count=0,
            token_contribution=52.0,
        ),
        MemberScenarioRow(
            member_hostname="niosx-member.example.com",
            group="niosx",
            ddi_count=800,
            active_ip_count=300,
            asset_count=0,
            token_contribution=55.08,
        ),
    ]
    from cloud_usage.nios.scenarios import MigrationSplitConfig
    split_config = MigrationSplitConfig(
        niosx_members=("niosx-member.example.com",),
        default_group="nios",
        assignment_source="dashboard",
    )
    return ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=hybrid_uddi,
        member_attribution=member_attribution,
        migration_split_used=split_config,
    )


class TestScenarioBreakdown:
    """Phase 19 — BRKDN-01 and BRKDN-02: Inline formula derivation in scenario cards."""

    def _complete_state_with_suite(self, suite):
        """Return a started TestClient with nios_manager in COMPLETE state and the given suite."""
        app = create_app()
        client = TestClient(app)
        client.__enter__()
        client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
        client.app.state.nios_manager.start()
        client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
        return client

    def test_current_grid_shows_ddi_formula(self) -> None:
        """BRKDN-02: Current Grid card shows 'DDI ÷ 50' formula string."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "DDI ÷ 50" in r.text

    def test_full_migration_shows_ddi_formula(self) -> None:
        """BRKDN-02: Full Migration card shows 'DDI ÷ 25' formula string."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "DDI ÷ 25" in r.text

    def test_comma_formatted_ddi_count(self) -> None:
        """BRKDN-02: DDI count >= 1000 is formatted with comma thousands separator."""
        suite = _make_scenario_suite_no_hybrid()  # ddi_count=1234
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "1,234" in r.text  # comma-formatted DDI count

    def test_current_grid_shows_ip_formula(self) -> None:
        """BRKDN-02: Current Grid card shows 'IPs ÷ 25' formula string."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "IPs ÷ 25" in r.text

    def test_full_migration_shows_ip_formula(self) -> None:
        """BRKDN-02: Full Migration card shows 'IPs ÷ 13' formula string."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "IPs ÷ 13" in r.text

    def test_assets_row_absent_when_zero(self) -> None:
        """BRKDN-01: Assets row is not rendered when asset_count == 0."""
        suite = _make_scenario_suite_no_hybrid()  # asset_count=0
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "Assets ÷" not in r.text

    def test_hero_tokens_still_present(self) -> None:
        """hero-tokens span preserved after adding breakdown rows."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "hero-tokens" in r.text

    def test_hybrid_card_absent_when_no_hybrid(self) -> None:
        """Hybrid UDDI card does not appear when hybrid_uddi is None."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "NIOS-remaining" not in r.text
            assert "NIOSX-migrated" not in r.text

    def test_hybrid_card_renders_sub_blocks(self) -> None:
        """Hybrid UDDI card shows NIOS-remaining and NIOSX-migrated sub-blocks."""
        suite = _make_scenario_suite_with_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "NIOS-remaining" in r.text
            assert "NIOSX-migrated" in r.text

    def test_breakdown_absent_when_no_scenario_suite(self) -> None:
        """No breakdown rows rendered when scenario_suite is None (non-complete state)."""
        app = create_app()
        with TestClient(app) as client:
            # IDLE state — no scenario_suite
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "DDI ÷" not in r.text


# ---------------------------------------------------------------------------
# Phase 19 — BRKDN-03, BRKDN-04: Member attribution table
# ---------------------------------------------------------------------------


class TestMemberAttribution:
    """Phase 19 — BRKDN-03 and BRKDN-04: Per-member breakdown table with group labels."""

    def test_member_attribution_section_present(self) -> None:
        """BRKDN-03: 'Member Attribution' heading is rendered in complete state."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "Member Attribution" in r.text

    def test_member_hostname_in_table(self) -> None:
        """BRKDN-03: Member hostname appears in the attribution table."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "grid-master.example.com" in r.text
            assert "member-01.example.com" in r.text

    def test_nios_group_label_rendered(self) -> None:
        """BRKDN-04: NIOS group label is rendered for nios-group members."""
        suite = _make_scenario_suite_no_hybrid()  # all members group="nios"
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "NIOS" in r.text

    def test_niosx_group_label_rendered(self) -> None:
        """BRKDN-04: NIOSX group label is rendered for niosx-group members."""
        suite = _make_scenario_suite_with_hybrid()  # has one niosx member
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "NIOSX" in r.text

    def test_all_nios_when_no_split(self) -> None:
        """BRKDN-04: When no hybrid split configured, all members show 'NIOS' label."""
        suite = _make_scenario_suite_no_hybrid()  # no hybrid, all group="nios"
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            # NIOS should appear (as group labels), NIOSX should not appear in group column
            assert "NIOS" in r.text
            # "NIOSX" label string should NOT appear (no niosx members in this suite)
            assert "NIOSX" not in r.text

    def test_scrollable_container_present(self) -> None:
        """BRKDN-03: Member table is wrapped in a scrollable container."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "overflow-y" in r.text

    def test_lease_only_note_present(self) -> None:
        """BRKDN-03: Subtitle note about lease-only per-member IPs is visible."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "lease-only" in r.text

    def test_run_another_button_after_attribution(self) -> None:
        """'Run Another Analysis' button still present after member attribution section."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "Run Another Analysis" in r.text
            # Both "Member Attribution" and "Run Another Analysis" must be present
            # and attribution must come before the button in the document
            pos_attribution = r.text.find("Member Attribution")
            pos_run_another = r.text.find("Run Another Analysis")
            assert pos_attribution < pos_run_another

    def test_table_columns_present(self) -> None:
        """BRKDN-03: Table headers include Member, Group, DDI Objects, Active IPs, Token Contribution."""
        suite = _make_scenario_suite_no_hybrid()
        app = create_app()
        with TestClient(app) as client:
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "backup.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete("/tmp/fake.xlsx", scenario_suite=suite)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "DDI Objects" in r.text
            assert "Active IPs" in r.text
            assert "Token Contribution" in r.text

    def test_member_attribution_absent_without_scenario_suite(self) -> None:
        """Member Attribution section not rendered when scenario_suite is None."""
        app = create_app()
        with TestClient(app) as client:
            # IDLE state — no scenario_suite
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "Member Attribution" not in r.text


# ---------------------------------------------------------------------------
# Phase 22: HTML content tests for Object Family Breakdown section
# ---------------------------------------------------------------------------


def _make_fake_family_breakdown():
    """Build a minimal family_breakdown list for rendering tests.

    Includes:
    - host_object: DDI family, ddi_adjusted reflects expansion
    - dns_record_a: DDI family, ddi_adjusted == raw_count
    - lease: non-DDI family with reason 'Active IP source only'
    - member: non-DDI family with reason 'Metadata only'
    """
    return [
        {
            "family": "host_object",
            "display_name": "host_object",
            "raw_count": 100,
            "ddi_adjusted": 220,
            "is_ddi": True,
            "reason": "",
        },
        {
            "family": "dns_record_a",
            "display_name": "dns_record_a",
            "raw_count": 500,
            "ddi_adjusted": 500,
            "is_ddi": True,
            "reason": "",
        },
        {
            "family": "lease",
            "display_name": "lease",
            "raw_count": 1000,
            "ddi_adjusted": 0,
            "is_ddi": False,
            "reason": "Active IP source only",
        },
        {
            "family": "member",
            "display_name": "member",
            "raw_count": 5,
            "ddi_adjusted": 0,
            "is_ddi": False,
            "reason": "Metadata only",
        },
    ]


class TestNiosCompleteFamilyBreakdown:
    """HTML content tests for Phase 22 Object Family Breakdown section.

    ANA-01: Section present listing non-zero families.
    ANA-02: DDI Adjusted column shows DDI-adjusted counts.
    ANA-03: DDI? column shows Yes/No.
    ANA-04: Reason column shows reason strings for non-DDI families.
    ANA-05: DDI Subtotal row present in tfoot.
    ANA-06: Section heading and scenario-independence subtext present.
    """

    def _nios_complete_with_breakdown(self, breakdown=None):
        """Set up TestClient with nios_manager in COMPLETE state with family_breakdown."""
        app = create_app()
        client = TestClient(app)
        client.__enter__()
        suite = _make_scenario_suite_no_hybrid()
        client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "fake.tar.gz")
        client.app.state.nios_manager.start()
        if breakdown is None:
            breakdown = _make_fake_family_breakdown()

        # Create a temp xlsx file so download link works
        os.makedirs("output", exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(dir="output", suffix=".xlsx", delete=False, prefix="nios_test_")
        tmp.close()
        client.app.state.nios_manager.set_complete(
            tmp.name,
            scenario_suite=suite,
            family_breakdown=breakdown,
        )
        return client

    def test_section_heading_present(self) -> None:
        """GET /tab/nios in COMPLETE state contains 'Object Family Breakdown' heading."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "Object Family Breakdown" in r.text

    def test_scenario_independence_subtext_present(self) -> None:
        """Section subtext states breakdown is scenario-independent (ANA-06)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "Scenario-independent" in r.text

    def test_family_names_present(self) -> None:
        """Family names from breakdown appear in the rendered table (ANA-01)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "host_object" in r.text
        assert "dns_record_a" in r.text
        assert "lease" in r.text

    def test_ddi_adjusted_column_present(self) -> None:
        """'DDI Adjusted' column header appears in the table (ANA-02)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "DDI Adjusted" in r.text

    def test_ddi_yes_present_for_ddi_families(self) -> None:
        """DDI? column shows 'Yes' for DDI-contributing families (ANA-03)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "Yes" in r.text

    def test_ddi_no_present_for_non_ddi_families(self) -> None:
        """DDI? column shows 'No' for non-DDI families (ANA-03)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "No" in r.text

    def test_reason_active_ip_source_present(self) -> None:
        """Reason column shows 'Active IP source only' for lease family (ANA-04)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "Active IP source only" in r.text

    def test_reason_metadata_only_present(self) -> None:
        """Reason column shows 'Metadata only' for member family (ANA-04)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "Metadata only" in r.text

    def test_ddi_subtotal_row_present(self) -> None:
        """tfoot DDI Subtotal row is present in the table (ANA-05)."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "DDI Subtotal" in r.text

    def test_section_absent_when_no_breakdown(self) -> None:
        """Object Family Breakdown section is absent when family_breakdown is None (ANA-01 guard)."""
        app = create_app()
        with TestClient(app) as client:
            suite = _make_scenario_suite_no_hybrid()
            os.makedirs("output", exist_ok=True)
            tmp = tempfile.NamedTemporaryFile(dir="output", suffix=".xlsx", delete=False, prefix="nios_nobd_")
            tmp.close()
            client.app.state.nios_manager.set_upload("/tmp/fake.tar.gz", "fake.tar.gz")
            client.app.state.nios_manager.start()
            client.app.state.nios_manager.set_complete(tmp.name, scenario_suite=suite, family_breakdown=None)
            r = client.get("/tab/nios")
            assert r.status_code == 200
            assert "Object Family Breakdown" not in r.text

    def test_section_between_scenario_cards_and_member_attribution(self) -> None:
        """Object Family Breakdown appears between scenario cards and member attribution."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        text = r.text
        # All three sections present
        assert "Current Grid" in text
        assert "Object Family Breakdown" in text
        assert "Member Attribution" in text
        # Order: scenario info comes before breakdown, breakdown comes before attribution
        scenario_pos = text.find("Current Grid")
        breakdown_pos = text.find("Object Family Breakdown")
        attribution_pos = text.find("Member Attribution")
        assert scenario_pos < breakdown_pos < attribution_pos, (
            f"Expected order: scenario ({scenario_pos}) < breakdown ({breakdown_pos}) < attribution ({attribution_pos})"
        )

    def test_raw_count_column_present(self) -> None:
        """Raw Count column header appears in the table."""
        client = self._nios_complete_with_breakdown()
        r = client.get("/tab/nios")
        assert r.status_code == 200
        assert "Raw Count" in r.text
