"""In-memory cache of ``SearchResponse`` messages, fed by a background SQS
consumer. Used by the local ``GET /results/{request_id}`` route so the FE can
poll for completion the same way it does against the cloud API.

This is intentionally local-only: in cloud, the ``ranking_and_rendering``
Lambda writes to DynamoDB and a dedicated ``results-api`` Lambda serves
``GET /results/{id}``.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from shared.schemas import SearchResponse
from shared.settings import settings
from shared.sqs import consume

log = logging.getLogger("api_gateway.results")

# Keep results around long enough for the FE polling window (90 × 2s = 3 min),
# plus a buffer for slow clients. Anything older gets evicted on access.
_TTL_SECONDS = 600


class ResultsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}

    def put(self, request_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._data[request_id] = (time.time(), payload)
            self._evict_locked()

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._data.get(request_id)
            if row is None:
                return None
            ts, payload = row
            if time.time() - ts > _TTL_SECONDS:
                self._data.pop(request_id, None)
                return None
            return payload

    def _evict_locked(self) -> None:
        now = time.time()
        stale = [k for k, (ts, _) in self._data.items() if now - ts > _TTL_SECONDS]
        for k in stale:
            self._data.pop(k, None)


store = ResultsStore()


def _consumer_loop() -> None:
    """Long-poll ``search-responses`` forever, caching each message by id."""
    while True:
        try:
            for msg in consume(settings.queue_search_responses, SearchResponse):
                store.put(msg.request_id, msg.model_dump())
                log.info("cached result for request_id=%s", msg.request_id)
        except Exception:
            # Don't let a transient SQS hiccup kill the gateway — log and retry.
            log.exception("search-responses consumer crashed; restarting in 2s")
            time.sleep(2)


def start_consumer() -> None:
    t = threading.Thread(
        target=_consumer_loop,
        name="search-responses-consumer",
        daemon=True,
    )
    t.start()
    log.info("started search-responses consumer thread")
