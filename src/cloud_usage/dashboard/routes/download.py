"""File download endpoints for XLS, CSV, and JSON reports.

Serves generated output files with path traversal protection.
Only allows downloading files with approved extensions that exist
within the configured output directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()

# Allowed file extensions for download
_ALLOWED_EXTENSIONS = {".xlsx", ".csv", ".json"}

# Default output directory
_OUTPUT_DIR = Path("output")


@router.get("/download/{filename}")
async def download_file(request: Request, filename: str) -> FileResponse:
    """Serve a file from the output directory.

    Validates filename to prevent path traversal attacks and only allows
    downloading files with approved extensions (.xlsx, .csv, .json).

    Args:
        request: The incoming HTTP request.
        filename: Name of the file to download.

    Returns:
        FileResponse for browser download, or 404/400 JSONResponse.
    """
    # Security: prevent path traversal
    if os.path.basename(filename) != filename:
        return JSONResponse(
            {"error": "Invalid filename"},
            status_code=400,
        )

    # Check extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in _ALLOWED_EXTENSIONS:
        return JSONResponse(
            {"error": f"File type not allowed: {ext}"},
            status_code=400,
        )

    file_path = _OUTPUT_DIR / filename

    # Verify file exists and is within output directory
    try:
        resolved = file_path.resolve()
        output_resolved = _OUTPUT_DIR.resolve()
        if not str(resolved).startswith(str(output_resolved)):
            return JSONResponse(
                {"error": "Invalid file path"},
                status_code=400,
            )
    except (ValueError, OSError):
        return JSONResponse(
            {"error": "Invalid file path"},
            status_code=400,
        )

    if not file_path.is_file():
        return JSONResponse(
            {"error": "File not found"},
            status_code=404,
        )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/api/downloads")
async def list_downloads(request: Request) -> JSONResponse:
    """Return list of available download files from scan results.

    Reads output_paths from scan_manager and returns as JSON with
    download URLs.

    Args:
        request: The incoming HTTP request.

    Returns:
        JSON list of available download files with URLs.
    """
    scan_manager = request.app.state.scan_manager
    output_paths = scan_manager.output_paths

    downloads = []
    for file_type, file_path in output_paths.items():
        filename = os.path.basename(file_path)
        downloads.append({
            "type": file_type,
            "filename": filename,
            "url": f"/download/{filename}",
        })

    return JSONResponse({"downloads": downloads})
