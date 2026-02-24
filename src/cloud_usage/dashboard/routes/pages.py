"""Full-page HTML routes for the dashboard.

Serves the base HTML page at the root URL. Content blocks will be
filled by subsequent plans (tab bar, progress, results, summary).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the base dashboard page.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered base.html template.
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "base.html")
