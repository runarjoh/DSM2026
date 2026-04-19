"""Run lifecycle and state management."""

from __future__ import annotations

import asyncio
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal


@dataclass
class RunState:
    status: Literal["running", "done", "error", "cancelled"] = "running"
    queue: queue.Queue = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    created_at: datetime = field(default_factory=datetime.now)
    result: dict[str, Any] | None = None
    error: str | None = None


class RunManager:
    """Thread-safe registry of active and recent runs.

    Enforces one-active-run-at-a-time.
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def create_run(self) -> tuple[str, RunState]:
        """Create a new run.  Raises RuntimeError if one is already running."""
        with self._lock:
            for rs in self._runs.values():
                if rs.status == "running":
                    raise RuntimeError("A run is already in progress")
            run_id = uuid.uuid4().hex[:12]
            state = RunState()
            self._runs[run_id] = state
            return run_id, state

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def cleanup_stale(self, max_age_minutes: int = 30) -> int:
        """Remove completed/errored/cancelled runs older than *max_age_minutes*."""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        removed = 0
        with self._lock:
            to_remove = [
                rid
                for rid, rs in self._runs.items()
                if rs.status in ("done", "error", "cancelled") and rs.created_at < cutoff
            ]
            for rid in to_remove:
                del self._runs[rid]
                removed += 1
        return removed


# Singleton used by all routes
run_manager = RunManager()


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

async def sse_generator(run_state: RunState):
    """Async generator that bridges *run_state.queue* → SSE ``data:`` lines.

    Polls the thread-safe queue via run_in_executor with a 0.5 s timeout,
    yielding each dict as a JSON SSE event.  Terminates on ``done``, ``error``,
    or ``cancelled`` event types.
    """
    import json

    loop = asyncio.get_event_loop()
    terminal_types = {"done", "error", "cancelled"}

    while True:
        try:
            event = await loop.run_in_executor(
                None, run_state.queue.get, True, 0.5
            )
        except queue.Empty:
            # If the run is no longer running and the queue is empty, stop
            if run_state.status != "running":
                break
            continue

        yield json.dumps(event)

        if event.get("type") in terminal_types:
            break
