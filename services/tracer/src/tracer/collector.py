"""Background collectors: follow docker logs of every container in the
compose project and feed parsed entries into the trace store.

One worker thread per container. Each thread iterates the streamed log
output from the docker engine and matches lines containing a recognisable
``request_id=<uuid>`` (or JSON ``"request_id":"<uuid>"``) pattern.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import UTC, datetime

import docker
from docker.errors import NotFound
from docker.models.containers import Container

from tracer.store import LogEntry, TraceStore

log = logging.getLogger("tracer.collector")

COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"
SELF_SERVICE = "tracer"

REQUEST_ID_RE = re.compile(
    r"""request_id["']?\s*[:=]\s*["']?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})""",
    re.IGNORECASE,
)


def _parse_line(raw: bytes) -> tuple[str, str] | None:
    """Split a docker-streamed log line into (timestamp, message).

    With ``timestamps=True`` docker prepends an RFC3339 timestamp + space.
    """
    try:
        text = raw.decode("utf-8", errors="replace").rstrip("\n")
    except Exception:
        return None
    if not text:
        return None
    ts, sep, msg = text.partition(" ")
    if sep == "":
        return datetime.now(UTC).isoformat(), text
    return ts, msg


def _follow_container(container: Container, store: TraceStore) -> None:
    service = container.labels.get(SERVICE_LABEL, container.name)
    if service == SELF_SERVICE:
        return
    log.info("following container service=%s id=%s", service, container.short_id)
    try:
        stream = container.logs(stream=True, follow=True, timestamps=True, tail=0)
        for raw in stream:
            parsed = _parse_line(raw)
            if parsed is None:
                continue
            ts, msg = parsed
            for match in REQUEST_ID_RE.finditer(msg):
                request_id = match.group(1)
                store.add(
                    request_id,
                    LogEntry(timestamp=ts, service=service, line=msg),
                )
    except NotFound:
        log.info("container gone service=%s", service)
    except Exception as e:
        log.warning("log follow error service=%s err=%s", service, e)


class CollectorManager:
    """Discovers compose-project containers and runs one follower per container."""

    def __init__(self, store: TraceStore, project: str = "inmobiliaria") -> None:
        self._store = store
        self._project = project
        self._client = docker.from_env()
        self._followed: set[str] = set()
        self._stop = threading.Event()
        self._discovery: threading.Thread | None = None

    def start(self) -> None:
        self._discovery = threading.Thread(target=self._discover_loop, name="tracer-discovery", daemon=True)
        self._discovery.start()

    def stop(self) -> None:
        self._stop.set()

    def _discover_loop(self) -> None:
        while not self._stop.is_set():
            try:
                containers = self._client.containers.list(filters={"label": f"{COMPOSE_PROJECT_LABEL}={self._project}"})
                for c in containers:
                    if c.id in self._followed:
                        continue
                    self._followed.add(c.id)
                    threading.Thread(
                        target=_follow_container,
                        args=(c, self._store),
                        name=f"tracer-follow-{c.short_id}",
                        daemon=True,
                    ).start()
            except Exception as e:
                log.warning("discovery error: %s", e)
            time.sleep(3)
