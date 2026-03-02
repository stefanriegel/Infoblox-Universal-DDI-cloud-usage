"""NIOS Grid analysis routes for the dashboard.

Implements the 2-step NIOS wizard:
  Step 1 (upload): Accept .tar.gz backup, save to disk, enumerate members
  Step 2 (run): Accept niosx_member toggles, dispatch background pipeline, stream SSE

All blocking NIOS pipeline calls run in background threads via
loop.run_in_executor(None, ...) for Python 3.9 compatibility.

Route list:
  POST /nios/upload  -- save backup file, return member list (step1_upload.html)
  POST /nios/run     -- dispatch pipeline, return SSE progress (step2_run.html)
  GET  /api/sse/nios -- stream NiosEventBridge events as text/event-stream

State is tracked via app.state.nios_manager (NiosScanManager).
SSE events are pushed via app.state.nios_event_bridge (separate EventBridge
instance -- never shared with cloud scan, per SC-5).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

if TYPE_CHECKING:
    from cloud_usage.dashboard.services.event_bridge import EventBridge
    from cloud_usage.dashboard.services.nios_manager import NiosScanManager

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Sync helpers (called via run_in_executor)
# ---------------------------------------------------------------------------


def _get_member_counts_sync(backup_path: str) -> list[dict]:
    """Parse backup, count DHCP leases per member, and return member list.

    Runs the full parse -> filter -> count pipeline to obtain both the
    member hostname map and per-member DHCP lease counts.

    Args:
        backup_path: Path to the saved .tar.gz NIOS Grid backup file.

    Returns:
        List of dicts with keys "virtual_oid", "hostname", "lease_count",
        sorted ascending by hostname.
    """
    from cloud_usage.nios.counter import count_objects
    from cloud_usage.nios.filter import FilterConfig, filter_objects
    from cloud_usage.nios.parser import get_member_map, parse_backup

    member_map = get_member_map(backup_path)  # {virtual_oid: hostname}

    filter_config = FilterConfig(
        whitelist=(),
        blacklist=(),
        lease_states=("active",),
    )

    raw_stream = parse_backup(backup_path)
    filtered = filter_objects(raw_stream, filter_config)
    count_result = count_objects(filtered, filter_config)

    # Build {hostname: lease_count} from member_counts, excluding the __grid__ sentinel
    lease_by_hostname: dict[str, int] = {
        mc.member_hostname: mc.lease_count
        for mc in count_result.member_counts
        if mc.member_hostname != "__grid__"
    }

    members = []
    for virtual_oid, hostname in member_map.items():
        members.append(
            {
                "virtual_oid": virtual_oid,
                "hostname": hostname,
                "lease_count": lease_by_hostname.get(hostname, 0),
            }
        )

    members.sort(key=lambda m: m["hostname"])
    return members


def _run_nios_pipeline(
    nios_manager: "NiosScanManager",
    backup_path: str,
    niosx_members: tuple,
    nios_event_bridge: "EventBridge",
) -> None:
    """Run the full NIOS analysis pipeline in a background thread.

    Inlines the pipeline (does NOT call run_nios_analysis()) so that the
    ScenarioSuite is captured for the summary card before writing the report.

    Pipeline:
      1. inspect_backup()    -- extract nios_version, snapshot_date
      2. get_member_map()    -- {virtual_oid: hostname}
      3. Pass A: parse -> filter -> count_objects -> CountResult
      4. Pass B: parse -> filter -> _count_ip_by_type -> ip_by_type
      5. compute_scenarios() -- ScenarioSuite (captured for nios_manager)
      6. write_nios_xlsx_report() -- write .xlsx
      7. nios_manager.set_complete(output_path, scenario_suite)

    On any exception: nios_manager.set_error(str(exc)) and log via logger.exception.
    In finally: always emit "nios_complete" then emit_done() to close SSE stream.

    Args:
        nios_manager: NiosScanManager for state/result storage.
        backup_path: Path to the saved .tar.gz backup file.
        niosx_members: Tuple of hostnames assigned to the UDDI group.
        nios_event_bridge: Dedicated EventBridge for NIOS SSE events.
    """
    from cloud_usage.nios.counter import count_objects
    from cloud_usage.nios.filter import FilterConfig, filter_objects
    from cloud_usage.nios.output import _count_ip_by_type, write_nios_xlsx_report
    from cloud_usage.nios.parser import get_member_map, inspect_backup, parse_backup
    from cloud_usage.nios.scenarios import MigrationSplitConfig, compute_scenarios

    try:
        start_time = time.monotonic()

        # Step 1: Inspect backup for metadata
        nios_event_bridge.emit("nios_progress", {
            "step": 1,
            "total": 6,
            "label": "Inspecting backup",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        })
        integrity = inspect_backup(backup_path)

        # Step 2: Build member map for Member Attribution sheet
        nios_event_bridge.emit("nios_progress", {
            "step": 2,
            "total": 6,
            "label": "Reading members",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        })
        member_map = get_member_map(backup_path)

        # Shared filter config
        filter_config = FilterConfig(
            whitelist=(),
            blacklist=(),
            lease_states=("active",),
        )

        # Step 3 (Pass A): parse -> filter -> count
        nios_event_bridge.emit("nios_progress", {
            "step": 3,
            "total": 6,
            "label": "Counting objects",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        })
        raw_stream_a = parse_backup(backup_path)
        filtered_a = filter_objects(raw_stream_a, filter_config)
        count_result = count_objects(filtered_a, filter_config)

        # Step 4 (Pass B): parse -> filter -> ip_by_type
        nios_event_bridge.emit("nios_progress", {
            "step": 4,
            "total": 6,
            "label": "Counting IP records",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        })
        raw_stream_b = parse_backup(backup_path)
        filtered_b = filter_objects(raw_stream_b, filter_config)
        ip_by_type = _count_ip_by_type(filtered_b, set(filter_config.lease_states))

        # Step 5: compute scenarios — capture suite for summary card
        nios_event_bridge.emit("nios_progress", {
            "step": 5,
            "total": 6,
            "label": "Computing scenarios",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        })
        split_config = MigrationSplitConfig(
            niosx_members=niosx_members,
            default_group="nios",
            assignment_source="dashboard",
        )
        scenario_suite = compute_scenarios(count_result, split_config)

        # Step 6: resolve output path and write report
        nios_event_bridge.emit("nios_progress", {
            "step": 6,
            "total": 6,
            "label": "Writing report",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        })
        analysis_timestamp = datetime.now(tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        os.makedirs("output", exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = f"output/nios_analysis_{ts}.xlsx"

        write_nios_xlsx_report(
            filepath=output_path,
            integrity_report=integrity,
            count_result=count_result,
            scenario_suite=scenario_suite,
            filter_config=filter_config,
            split_config=split_config,
            analysis_timestamp=analysis_timestamp,
            member_map=member_map,
            ip_by_type=ip_by_type,
        )

        # Step 7: record success
        nios_manager.set_complete(output_path, scenario_suite=scenario_suite)
        logger.info("NIOS analysis complete: %s", output_path)

    except Exception as exc:
        logger.exception("NIOS pipeline failed: %s", exc)
        nios_manager.set_error(str(exc))

    finally:
        # Always signal SSE completion to close the browser SSE connection
        try:
            nios_event_bridge.emit("nios_complete", {})
            nios_event_bridge.emit_done()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("/nios/upload", response_class=HTMLResponse)
async def nios_upload(request: Request, file: UploadFile) -> HTMLResponse:
    """Accept a NIOS Grid backup .tar.gz and return the member list.

    Saves the uploaded file to output/nios_upload_<timestamp>.tar.gz before
    dispatching any background work (SC-4 requirement). Resets prior analysis
    state on every upload. Runs _get_member_counts_sync in a background thread
    to enumerate Grid members with DHCP lease counts for Step 1 display.

    Args:
        request: The incoming HTTP request.
        file: Uploaded .tar.gz NIOS Grid backup file.

    Returns:
        Rendered partials/nios/step1_upload.html with member list.
    """
    nios_manager = request.app.state.nios_manager
    templates = request.app.state.templates

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    save_path = f"output/nios_upload_{timestamp}.tar.gz"

    # SC-4: save file to disk within the request handler
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    original_filename = file.filename or "backup.tar.gz"
    nios_manager.set_upload(save_path, filename=original_filename)
    nios_manager.reset()

    members: list[dict] = []
    error_msg: str = ""

    try:
        loop = asyncio.get_running_loop()
        members = await loop.run_in_executor(
            None, _get_member_counts_sync, save_path
        )
    except Exception as exc:
        logger.exception("Failed to enumerate NIOS members: %s", exc)
        error_msg = str(exc)

    return templates.TemplateResponse(
        request,
        "partials/nios/step1_upload.html",
        {
            "request": request,
            "members": members,
            "filename": original_filename,
            "error_msg": error_msg,
            "nios_state": nios_manager.state.value,
        },
    )


@router.post("/nios/run", response_class=HTMLResponse)
async def nios_run(request: Request) -> HTMLResponse:
    """Accept NIOSX member toggles and dispatch the NIOS analysis pipeline.

    Validates that a backup has been uploaded and that no analysis is currently
    running. Dispatches _run_nios_pipeline via loop.run_in_executor for Python
    3.9 compatibility (asyncio.to_thread requires 3.10+).

    Args:
        request: The incoming HTTP request with niosx_member form fields.

    Returns:
        Rendered partials/nios/step2_run.html with running state, or 400/409 on error.
    """
    from fastapi.responses import JSONResponse

    nios_manager = request.app.state.nios_manager
    nios_event_bridge = request.app.state.nios_event_bridge
    templates = request.app.state.templates

    if not nios_manager.can_start():
        return JSONResponse(
            {"error": "Analysis already running"},
            status_code=409,
        )

    backup_path = nios_manager.upload_path
    if backup_path is None:
        return JSONResponse(
            {"error": "No backup uploaded. Please upload a .tar.gz file first."},
            status_code=400,
        )

    form = await request.form()
    niosx_members = tuple(form.getlist("niosx_member"))

    nios_manager.start()

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _run_nios_pipeline,
        nios_manager,
        backup_path,
        niosx_members,
        nios_event_bridge,
    )

    return templates.TemplateResponse(
        request,
        "partials/nios/step2_run.html",
        {
            "request": request,
            "nios_state": "running",
        },
    )


@router.get("/api/sse/nios")
async def sse_nios(request: Request) -> StreamingResponse:
    """Stream NIOS analysis events as Server-Sent Events.

    Subscribes to the dedicated NiosEventBridge (never shared with cloud scan
    SSE, per SC-5) and yields SSE-formatted strings until the analysis completes
    or the client disconnects.

    Race-condition guard: if the background pipeline finishes before the browser
    establishes this SSE connection, nios_manager.state is already COMPLETE or
    ERROR and the nios_complete event was emitted to an empty subscriber list
    (silently dropped). In that case, emit nios_complete immediately so the
    browser tab refresh fires even for fast pipelines.

    Args:
        request: The incoming HTTP request.

    Returns:
        StreamingResponse with text/event-stream media type.
    """
    from cloud_usage.dashboard.services.nios_manager import NiosState

    nios_event_bridge = request.app.state.nios_event_bridge
    nios_manager = request.app.state.nios_manager

    async def event_generator():
        """Yield SSE-formatted event strings from the NIOS EventBridge."""
        # Guard: pipeline may have finished before SSE connection was opened.
        # If state is already terminal, emit nios_complete immediately.
        if nios_manager.state in (NiosState.COMPLETE, NiosState.ERROR):
            yield "event: nios_complete\ndata: {}\n\n"
            return

        async for event_str in nios_event_bridge.subscribe():
            if await request.is_disconnected():
                break
            yield event_str

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
