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

    def test_upload_response_contains_virtual_oid_and_lease_count(self) -> None:
        """POST /nios/upload HTML response contains virtual_oid and lease_count values."""
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
                assert "150" in r.text  # lease_count for grid-master

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
                # step2_run.html contains running indicator
                assert "running" in r.text.lower() or "NIOS" in r.text

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
