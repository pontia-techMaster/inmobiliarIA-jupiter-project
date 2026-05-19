import importlib
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from tracer.store import LogEntry, Trace

REQUEST_ID = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def tracer_main(monkeypatch):
    """
    Importa tracer.main con docker.from_env mockeado.

    tracer.main crea CollectorManager al importarse, y CollectorManager llama
    a docker.from_env(). Por eso hay que parchearlo antes de importar main.
    """
    from tracer import collector as tracer_collector

    fake_docker_client = MagicMock()

    monkeypatch.setattr(
        tracer_collector.docker,
        "from_env",
        MagicMock(return_value=fake_docker_client),
    )

    sys.modules.pop("tracer.main", None)

    module = importlib.import_module("tracer.main")

    yield module

    sys.modules.pop("tracer.main", None)


def make_entry(
    timestamp="2026-05-09T10:00:00Z",
    service="api_gateway",
    line="request_id=123 message",
):
    return LogEntry(
        timestamp=timestamp,
        service=service,
        line=line,
    )


def test_index_returns_html(tracer_main):
    result = tracer_main.index()

    assert isinstance(result, str)
    assert "<!doctype html>" in result.lower()
    assert "Tracer" in result


def test_health_returns_ok(tracer_main):
    result = tracer_main.health()

    assert result == {"status": "ok"}


def test_traces_returns_empty_list(tracer_main, monkeypatch):
    class FakeStore:
        def recent(self, limit=50):
            assert limit == 10
            return []

    monkeypatch.setattr(tracer_main, "store", FakeStore())

    result = tracer_main.traces(limit=10)

    assert result == {"traces": []}


def test_traces_returns_trace_summaries(tracer_main, monkeypatch):
    trace_1 = Trace(
        request_id="req-1",
        entries=[
            make_entry(
                timestamp="2026-05-09T10:00:00Z",
                service="vector_query",
                line="first",
            ),
            make_entry(
                timestamp="2026-05-09T10:00:02Z",
                service="api_gateway",
                line="second",
            ),
            make_entry(
                timestamp="2026-05-09T10:00:03Z",
                service="vector_query",
                line="third",
            ),
        ],
    )

    trace_2 = Trace(
        request_id="req-2",
        entries=[
            make_entry(
                timestamp="2026-05-09T10:01:00Z",
                service="process_user_prompt",
                line="another",
            )
        ],
    )

    class FakeStore:
        def recent(self, limit=50):
            assert limit == 10
            return [trace_1, trace_2]

    monkeypatch.setattr(tracer_main, "store", FakeStore())

    result = tracer_main.traces(limit=10)

    assert result == {
        "traces": [
            {
                "request_id": "req-1",
                "first_seen": "2026-05-09T10:00:00Z",
                "last_seen": "2026-05-09T10:00:03Z",
                "services": ["api_gateway", "vector_query"],
                "entry_count": 3,
            },
            {
                "request_id": "req-2",
                "first_seen": "2026-05-09T10:01:00Z",
                "last_seen": "2026-05-09T10:01:00Z",
                "services": ["process_user_prompt"],
                "entry_count": 1,
            },
        ]
    }


def test_traces_handles_trace_without_entries(tracer_main, monkeypatch):
    trace = Trace(
        request_id="req-empty",
        entries=[],
    )

    class FakeStore:
        def recent(self, limit=50):
            return [trace]

    monkeypatch.setattr(tracer_main, "store", FakeStore())

    result = tracer_main.traces(limit=50)

    assert result == {
        "traces": [
            {
                "request_id": "req-empty",
                "first_seen": None,
                "last_seen": None,
                "services": [],
                "entry_count": 0,
            }
        ]
    }


def test_trace_returns_entries(tracer_main, monkeypatch):
    trace = Trace(
        request_id=REQUEST_ID,
        entries=[
            make_entry(
                timestamp="2026-05-09T10:00:00Z",
                service="api_gateway",
                line=f"request_id={REQUEST_ID} received",
            ),
            make_entry(
                timestamp="2026-05-09T10:00:01Z",
                service="vector_query",
                line=f"request_id={REQUEST_ID} searched",
            ),
        ],
    )

    class FakeStore:
        def get(self, request_id):
            assert request_id == REQUEST_ID
            return trace

    monkeypatch.setattr(tracer_main, "store", FakeStore())

    result = tracer_main.trace(REQUEST_ID)

    assert result == {
        "request_id": REQUEST_ID,
        "entries": [
            {
                "timestamp": "2026-05-09T10:00:00Z",
                "service": "api_gateway",
                "line": f"request_id={REQUEST_ID} received",
            },
            {
                "timestamp": "2026-05-09T10:00:01Z",
                "service": "vector_query",
                "line": f"request_id={REQUEST_ID} searched",
            },
        ],
    }


def test_trace_raises_404_when_missing(tracer_main, monkeypatch):
    class FakeStore:
        def get(self, request_id):
            return None

    monkeypatch.setattr(tracer_main, "store", FakeStore())

    with pytest.raises(HTTPException) as exc_info:
        tracer_main.trace("missing-request-id")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "trace not found (yet)"


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_collector(tracer_main, monkeypatch):
    calls = []

    class FakeCollector:
        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

    monkeypatch.setattr(tracer_main, "collector", FakeCollector())

    async with tracer_main.lifespan(tracer_main.app):
        assert calls == ["start"]

    assert calls == ["start", "stop"]
