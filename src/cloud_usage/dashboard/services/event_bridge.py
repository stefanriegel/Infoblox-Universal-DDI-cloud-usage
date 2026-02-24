"""Sync-to-async event bridge for SSE streaming.

Bridges synchronous orchestrator worker threads to async SSE consumers
using a janus Queue. Sync threads call emit() to push events; async SSE
handlers iterate subscribe() to yield SSE-formatted strings.

Supports multiple concurrent subscribers via per-subscriber fan-out queues.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

import janus


class EventBridge:
    """Bridges sync orchestrator threads to async SSE consumers.

    Uses janus.Queue for thread-safe sync-to-async communication.
    Supports multiple concurrent SSE subscribers via fan-out pattern:
    each subscriber gets its own janus.Queue, and emit() copies events
    to all active subscriber queues.

    Attributes:
        _queue: Main janus queue for incoming events.
        _subscribers: List of per-subscriber janus queues for fan-out.
        _lock: asyncio.Lock protecting subscriber list mutations.
    """

    def __init__(self) -> None:
        self._queue: janus.Queue[dict] | None = None
        self._subscribers: list[janus.Queue[dict]] = []
        self._lock: asyncio.Lock | None = None

    async def start(self) -> None:
        """Create the main queue and subscriber lock in async context."""
        self._queue = janus.Queue()
        self._lock = asyncio.Lock()

    def emit(self, event_type: str, data: dict) -> None:
        """Push an event from a sync worker thread. Thread-safe.

        Copies the event to all active subscriber queues for fan-out.

        Args:
            event_type: SSE event name (e.g., "progress_aws", "scan_complete").
            data: Event payload dict, will be JSON-serialized.
        """
        msg = {"event": event_type, "data": data}
        for sub in self._subscribers:
            try:
                sub.sync_q.put_nowait(msg)
            except Exception:
                pass  # Skip closed or full queues

    def emit_done(self) -> None:
        """Signal scan completion. Called from sync code."""
        self.emit("scan_complete", {})

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted strings.

        Creates a per-subscriber janus.Queue, registers it for fan-out,
        and yields SSE-formatted event strings. Sends keepalive comments
        every 25 seconds to prevent connection timeout (Pitfall 3).
        Breaks on scan_complete event. Unregisters queue on exit.

        Yields:
            SSE-formatted strings (e.g., "event: progress_aws\\ndata: {...}\\n\\n").
        """
        sub_queue: janus.Queue[dict] = janus.Queue()
        if self._lock is not None:
            async with self._lock:
                self._subscribers.append(sub_queue)

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(
                        sub_queue.async_q.get(), timeout=25.0
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                event_type = msg["event"]
                data_json = json.dumps(msg["data"])
                yield f"event: {event_type}\ndata: {data_json}\n\n"

                if event_type == "scan_complete":
                    break
        finally:
            if self._lock is not None:
                async with self._lock:
                    if sub_queue in self._subscribers:
                        self._subscribers.remove(sub_queue)
            sub_queue.close()
            await sub_queue.wait_closed()

    async def close(self) -> None:
        """Close all queues and clean up resources."""
        for sub in self._subscribers:
            sub.close()
            await sub.wait_closed()
        self._subscribers.clear()

        if self._queue is not None:
            self._queue.close()
            await self._queue.wait_closed()
            self._queue = None
