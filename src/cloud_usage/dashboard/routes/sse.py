"""SSE streaming endpoint for real-time progress updates.

Streams discovery progress events as Server-Sent Events using
FastAPI's StreamingResponse. Each event carries JSON data for
HTMX sse-swap to display per-provider progress bars in real time.

Headers set per Research Pitfall 3: Cache-Control no-cache,
Connection keep-alive, X-Accel-Buffering no to prevent proxy
buffering and idle connection timeouts.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/sse", tags=["sse"])


@router.get("/progress")
async def sse_progress(request: Request) -> StreamingResponse:
    """Stream discovery progress events as SSE.

    Subscribes to the EventBridge and yields SSE-formatted strings
    containing per-provider progress data. Checks for client
    disconnection to stop streaming when the browser closes.

    Args:
        request: The incoming HTTP request.

    Returns:
        StreamingResponse with text/event-stream media type.
    """
    event_bridge = request.app.state.event_bridge

    async def event_generator():
        """Yield SSE-formatted event strings from EventBridge."""
        async for event_str in event_bridge.subscribe():
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
