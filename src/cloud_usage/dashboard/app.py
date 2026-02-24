"""FastAPI app factory with lifespan, static mount, and route registration.

Creates the UDDI Cloud Usage Estimator dashboard application. Uses the
modern lifespan context manager pattern (not deprecated on_event) for
startup/shutdown lifecycle management of EventBridge and ScanManager.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cloud_usage.dashboard.routes.pages import router as pages_router
from cloud_usage.dashboard.routes.partials import router as partials_router
from cloud_usage.dashboard.routes.sse import router as sse_router
from cloud_usage.dashboard.services.event_bridge import EventBridge
from cloud_usage.dashboard.services.scan_manager import ScanManager

# Resolve paths relative to this file
_BASE_DIR = Path(__file__).parent
_STATIC_DIR = _BASE_DIR / "static"
_TEMPLATES_DIR = _BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage app lifecycle: start EventBridge + ScanManager on startup.

    Args:
        app: The FastAPI application instance.

    Yields:
        None after startup; runs shutdown on exit.
    """
    # Startup
    event_bridge = EventBridge()
    await event_bridge.start()
    app.state.event_bridge = event_bridge

    scan_manager = ScanManager()
    app.state.scan_manager = scan_manager

    app.state.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    yield

    # Shutdown
    await event_bridge.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI dashboard application.

    Sets up:
    - Lifespan manager for EventBridge and ScanManager
    - Static file serving from dashboard/static/
    - Jinja2 template engine pointing to dashboard/templates/
    - Page routes, HTMX partial routes, and SSE streaming routes

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="UDDI Cloud Usage Estimator",
        lifespan=lifespan,
    )

    # Mount static files
    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    # Include route modules
    app.include_router(pages_router)
    app.include_router(partials_router)
    app.include_router(sse_router)

    return app
