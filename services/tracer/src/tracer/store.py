"""In-memory bounded store of log entries indexed by request_id."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    timestamp: str
    service: str
    line: str


@dataclass
class Trace:
    request_id: str
    entries: list[LogEntry] = field(default_factory=list)


class TraceStore:
    """Thread-safe LRU-ish store: keeps the last ``capacity`` request_ids seen."""

    def __init__(self, capacity: int = 200) -> None:
        self._capacity = capacity
        self._traces: OrderedDict[str, Trace] = OrderedDict()
        self._lock = threading.Lock()

    def add(self, request_id: str, entry: LogEntry) -> None:
        with self._lock:
            trace = self._traces.get(request_id)
            if trace is None:
                trace = Trace(request_id=request_id)
                self._traces[request_id] = trace
                if len(self._traces) > self._capacity:
                    self._traces.popitem(last=False)
            else:
                self._traces.move_to_end(request_id)
            trace.entries.append(entry)

    def get(self, request_id: str) -> Trace | None:
        with self._lock:
            trace = self._traces.get(request_id)
            if trace is None:
                return None
            return Trace(request_id=trace.request_id, entries=list(trace.entries))

    def recent(self, limit: int = 50) -> list[Trace]:
        with self._lock:
            ids = list(self._traces.keys())[-limit:][::-1]
            return [
                Trace(
                    request_id=rid,
                    entries=list(self._traces[rid].entries),
                )
                for rid in ids
            ]
