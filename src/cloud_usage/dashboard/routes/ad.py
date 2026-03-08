"""Microsoft AD analysis routes for the dashboard.

Implements the AD wizard and progress streaming routes:
  POST /ad/run           -- Accept form data, build AdOptions, dispatch pipeline
  GET  /api/sse/ad       -- Stream AdEventBridge events as text/event-stream
  GET  /api/ad/progress  -- Return current progress as HTML fragment

All blocking AD pipeline calls run in background threads via
loop.run_in_executor(None, ...) for Python 3.9 compatibility
(asyncio.to_thread requires 3.10+).

State is tracked via app.state.ad_manager (AdScanManager).
SSE events are pushed via app.state.ad_event_bridge (separate EventBridge
instance -- never shared with cloud scan or NIOS, per SC-5).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

if TYPE_CHECKING:
    from cloud_usage.dashboard.services.ad_manager import AdScanManager
    from cloud_usage.dashboard.services.event_bridge import EventBridge

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Sync helpers (called via run_in_executor)
# ---------------------------------------------------------------------------


def _run_ad_pipeline(
    ad_manager: "AdScanManager",
    options,
    ad_event_bridge: "EventBridge",
) -> None:
    """Run the AD analysis pipeline in a background thread.

    Emits SSE progress events at two phases:
      Phase 1: Connecting (indeterminate — total=0)
      Phase 2: Writing report (determinate 2/2)

    run_ad_analysis() handles all per-DC querying internally.
    SSE hooks wrap the call so no changes to the AD provider package are needed.

    On any exception: ad_manager.set_error(str(exc)) and log via logger.exception.
    In finally: always emit "ad_complete" then emit_done() to close SSE stream.

    Args:
        ad_manager: AdScanManager for state/result storage.
        options: AdOptions with all connection parameters.
        ad_event_bridge: Dedicated EventBridge for AD SSE events.
    """
    import os
    import time
    from datetime import datetime, timezone

    from cloud_usage.counting.token_calculator import calculate_tokens
    from cloud_usage.providers.ad.runner import run_ad_analysis

    try:
        start_time = time.monotonic()

        # Phase 1: Connecting (indeterminate — total=0)
        ad_manager.set_progress(0, 0, "Connecting to AD\u2026", 0.0)
        ad_event_bridge.emit("ad_progress", ad_manager.current_progress)

        os.makedirs("output", exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = f"output/ad_analysis_{ts}.xlsx"

        resources, errors = run_ad_analysis(options, output_path=output_path)

        elapsed = round(time.monotonic() - start_time, 1)

        # Phase 2: Writing report (determinate 2 of 2)
        ad_manager.set_progress(2, 2, "Writing report\u2026", elapsed)
        ad_event_bridge.emit("ad_progress", ad_manager.current_progress)

        # Compute counts from resources
        dns_zone_count = sum(1 for r in resources if r.resource_type == "ad-dns-zone")
        dhcp_scope_count = sum(1 for r in resources if r.resource_type == "ad-dhcp-scope")
        user_count = sum(1 for r in resources if r.resource_type == "ad-user")
        ddi_count = sum(1 for r in resources if r.counted and r.category == "ddi")
        ip_count = sum(1 for r in resources if r.counted and r.category in ("ip", "asset"))
        token_result = calculate_tokens(ddi_count, ip_count, 0)

        ad_manager.set_complete(
            output_path=output_path,
            resources=resources,
            errors=errors,
            dns_zone_count=dns_zone_count,
            dhcp_scope_count=dhcp_scope_count,
            user_count=user_count,
            ddi_count=ddi_count,
            ip_count=ip_count,
            token_total=token_result["total_tokens"],
        )
        logger.info("AD analysis complete: %s", output_path)

    except Exception as exc:
        logger.exception("AD pipeline failed: %s", exc)
        ad_manager.set_error(str(exc))

    finally:
        # Always signal SSE completion to close the browser SSE connection
        try:
            ad_event_bridge.emit("ad_complete", {})
            ad_event_bridge.emit_done()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("/ad/run", response_class=HTMLResponse)
async def ad_run(request: Request) -> HTMLResponse:
    """Accept AD connection form and dispatch the AD analysis pipeline.

    Reads form fields, builds AdOptions, stores options for retry pre-fill,
    then dispatches _run_ad_pipeline via loop.run_in_executor for Python 3.9
    compatibility (asyncio.to_thread requires 3.10+).

    Pitfall guard (RESEARCH.md Pitfall 3): username = form.get("ad_username") or None
    converts empty string to None so Kerberos mode never passes empty strings to AdOptions.

    Args:
        request: The incoming HTTP request with AD wizard form fields.

    Returns:
        HTMLResponse with SSE connection div for HTMX wiring, or 409 if already running.
    """
    from fastapi.responses import JSONResponse

    from cloud_usage.providers.ad.options import AdOptions, normalize_ad_servers

    ad_manager = request.app.state.ad_manager
    ad_event_bridge = request.app.state.ad_event_bridge

    if not ad_manager.can_start():
        return JSONResponse(
            {"error": "Analysis already running"},
            status_code=409,
        )

    form = await request.form()

    # Build services list from checkboxes — getlist handles multi-value fields
    services_raw = form.getlist("services")
    if not services_raw:
        # Fallback: check individual named checkboxes for backward compat
        services_raw = []
        if form.get("ad_svc_dns"):
            services_raw.append("dns")
        if form.get("ad_svc_dhcp"):
            services_raw.append("dhcp")
        if form.get("ad_svc_user"):
            services_raw.append("user")
    if not services_raw:
        services_raw = ["dns", "dhcp", "user"]

    # Pitfall guard: convert empty string to None for Kerberos compatibility
    username = form.get("ad_username") or None
    password = form.get("ad_password") or None
    auth_mode = form.get("auth_mode", "kerberos")

    servers_str = form.get("servers", "")
    servers = normalize_ad_servers(servers_str)

    winrm_port_raw = form.get("winrm_port", "5985")
    try:
        winrm_port = int(winrm_port_raw)
    except (ValueError, TypeError):
        winrm_port = 5985

    winrm_ssl = bool(form.get("winrm_ssl"))
    autodiscover = bool(form.get("autodiscover"))
    discovery_server = form.get("discovery_server") or None

    options = AdOptions(
        servers=servers,
        auth_mode=auth_mode,
        username=username,
        password=password,
        winrm_port=winrm_port,
        winrm_ssl=winrm_ssl,
        autodiscover=autodiscover,
        discovery_server=discovery_server,
        services=tuple(services_raw),
    )

    # Store options for retry pre-fill BEFORE transitioning to RUNNING
    ad_manager.set_last_options(options)
    ad_manager.start()

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _run_ad_pipeline,
        ad_manager,
        options,
        ad_event_bridge,
    )

    # Return inline HTML with SSE connection div — no template needed for running state.
    # The full tab re-render fires when ad_complete SSE event triggers hx-get="/tab/ad".
    return HTMLResponse(content="""
<div hx-ext="sse" sse-connect="/api/sse/ad" id="ad-progress-container">
  <article>
    <header>Running AD Analysis</header>
    <progress></progress>
    <p>Connecting to Active Directory...</p>
  </article>
  <div sse-swap="ad_complete" hx-swap="none"
       hx-trigger="sse:ad_complete"
       hx-get="/tab/ad" hx-target="#tab-container"></div>
</div>
""")


@router.get("/api/sse/ad")
async def sse_ad(request: Request) -> StreamingResponse:
    """Stream AD analysis events as Server-Sent Events.

    Subscribes to the dedicated AdEventBridge (never shared with cloud scan
    or NIOS SSE, per SC-5) and yields SSE-formatted strings until the analysis
    completes or the client disconnects.

    Race-condition guard: if the background pipeline finishes before the browser
    establishes this SSE connection, ad_manager.state is already COMPLETE or
    ERROR and the ad_complete event was emitted to an empty subscriber list
    (silently dropped). In that case, emit ad_complete immediately so the
    browser tab refresh fires even for fast pipelines.

    Args:
        request: The incoming HTTP request.

    Returns:
        StreamingResponse with text/event-stream media type.
    """
    from cloud_usage.dashboard.services.ad_manager import AdState

    ad_event_bridge = request.app.state.ad_event_bridge
    ad_manager = request.app.state.ad_manager

    async def event_generator():
        """Yield SSE-formatted event strings from the AD EventBridge."""
        # Guard: pipeline may have finished before SSE connection was opened.
        # If state is already terminal, emit ad_complete immediately.
        if ad_manager.state in (AdState.COMPLETE, AdState.ERROR):
            yield "event: ad_complete\ndata: {}\n\n"
            return

        # Use aclose() to ensure generator cleanup on client disconnect.
        gen = ad_event_bridge.subscribe()
        try:
            while True:
                # Poll for both an event and client disconnect with a short
                # timeout so the test client can cleanly disconnect.
                disconnect_task = asyncio.ensure_future(request.is_disconnected())
                event_task = asyncio.ensure_future(gen.__anext__())
                try:
                    done, pending = await asyncio.wait(
                        [disconnect_task, event_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=1.0,
                    )
                    for t in pending:
                        t.cancel()
                        try:
                            await t
                        except (asyncio.CancelledError, StopAsyncIteration):
                            pass
                    if disconnect_task in done and disconnect_task.result():
                        break
                    if event_task in done:
                        try:
                            event_str = event_task.result()
                        except StopAsyncIteration:
                            break
                        yield event_str
                    # If timeout with no events, loop and check again
                except asyncio.CancelledError:
                    break
        finally:
            await gen.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/ad/progress", response_class=HTMLResponse)
async def ad_progress_display(request: Request) -> HTMLResponse:
    """Return current AD pipeline progress as an HTML fragment.

    Called by HTMX hx-get on sse:ad_progress events to render
    the progress bar, step label, and elapsed time. Always returns
    the latest state from AdScanManager.current_progress.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered partials/ad/progress_display.html fragment.
    """
    ad_manager = request.app.state.ad_manager
    templates = request.app.state.templates
    progress = ad_manager.current_progress
    return templates.TemplateResponse(
        request,
        "partials/ad/progress_display.html",
        {"request": request, "progress": progress},
    )
