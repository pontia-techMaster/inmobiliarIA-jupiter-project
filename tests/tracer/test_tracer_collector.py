from unittest.mock import MagicMock

from docker.errors import NotFound
from tracer import collector
from tracer.collector import (
    REQUEST_ID_RE,
    SELF_SERVICE,
    SERVICE_LABEL,
    CollectorManager,
    _follow_container,
    _parse_line,
)
from tracer.store import TraceStore

REQUEST_ID = "123e4567-e89b-12d3-a456-426614174000"


def test_parse_line_with_docker_timestamp():
    raw = b"2026-05-09T10:00:00.000000000Z " b"request_id=123e4567-e89b-12d3-a456-426614174000 message\n"

    result = _parse_line(raw)

    assert result == (
        "2026-05-09T10:00:00.000000000Z",
        "request_id=123e4567-e89b-12d3-a456-426614174000 message",
    )


def test_parse_line_without_timestamp_uses_current_time():
    raw = b"message-without-spaces"

    result = _parse_line(raw)

    assert result is not None

    timestamp, message = result

    assert isinstance(timestamp, str)
    assert message == "message-without-spaces"


def test_parse_line_empty_returns_none():
    result = _parse_line(b"\n")

    assert result is None


def test_parse_line_invalid_decode_returns_none():
    class BadRaw:
        def decode(self, *args, **kwargs):
            raise RuntimeError("decode failed")

    result = _parse_line(BadRaw())

    assert result is None


def test_request_id_regex_matches_equal_format():
    text = f"request_id={REQUEST_ID} hello"

    match = REQUEST_ID_RE.search(text)

    assert match is not None
    assert match.group(1) == REQUEST_ID


def test_request_id_regex_matches_colon_format():
    text = f"request_id:{REQUEST_ID} hello"

    match = REQUEST_ID_RE.search(text)

    assert match is not None
    assert match.group(1) == REQUEST_ID


def test_request_id_regex_matches_json_double_quotes_format():
    text = f'{{"request_id":"{REQUEST_ID}", "message": "hello"}}'

    match = REQUEST_ID_RE.search(text)

    assert match is not None
    assert match.group(1) == REQUEST_ID


def test_request_id_regex_matches_json_single_quotes_format():
    text = f"'request_id': '{REQUEST_ID}'"

    match = REQUEST_ID_RE.search(text)

    assert match is not None
    assert match.group(1) == REQUEST_ID


def test_request_id_regex_is_case_insensitive():
    text = f"REQUEST_ID={REQUEST_ID}"

    match = REQUEST_ID_RE.search(text)

    assert match is not None
    assert match.group(1) == REQUEST_ID


def test_request_id_regex_does_not_match_invalid_id():
    text = "request_id=not-a-valid-uuid"

    match = REQUEST_ID_RE.search(text)

    assert match is None


def test_follow_container_ignores_tracer_service():
    store = TraceStore()

    container = MagicMock()
    container.labels = {SERVICE_LABEL: SELF_SERVICE}
    container.name = SELF_SERVICE
    container.short_id = "abc123"

    result = _follow_container(container, store)

    assert result is None
    container.logs.assert_not_called()


def test_follow_container_adds_entries_for_request_id():
    store = TraceStore()

    container = MagicMock()
    container.labels = {SERVICE_LABEL: "api_gateway"}
    container.name = "api_gateway"
    container.short_id = "abc123"

    container.logs.return_value = [
        f"2026-05-09T10:00:00Z request_id={REQUEST_ID} first log\n".encode(),
        b"2026-05-09T10:00:01Z log without request id\n",
        f'2026-05-09T10:00:02Z {{"request_id":"{REQUEST_ID}"}} second log\n'.encode(),
    ]

    result = _follow_container(container, store)

    assert result is None

    trace = store.get(REQUEST_ID)

    assert trace is not None
    assert trace.request_id == REQUEST_ID
    assert len(trace.entries) == 2

    assert trace.entries[0].timestamp == "2026-05-09T10:00:00Z"
    assert trace.entries[0].service == "api_gateway"
    assert trace.entries[0].line == f"request_id={REQUEST_ID} first log"

    assert trace.entries[1].timestamp == "2026-05-09T10:00:02Z"
    assert trace.entries[1].service == "api_gateway"
    assert trace.entries[1].line == f'{{"request_id":"{REQUEST_ID}"}} second log'

    container.logs.assert_called_once_with(
        stream=True,
        follow=True,
        timestamps=True,
        tail=0,
    )


def test_follow_container_uses_container_name_when_service_label_missing():
    store = TraceStore()

    container = MagicMock()
    container.labels = {}
    container.name = "fallback_service"
    container.short_id = "abc123"

    container.logs.return_value = [f"2026-05-09T10:00:00Z request_id={REQUEST_ID} hello\n".encode()]

    _follow_container(container, store)

    trace = store.get(REQUEST_ID)

    assert trace is not None
    assert trace.entries[0].service == "fallback_service"


def test_follow_container_handles_not_found_error():
    store = TraceStore()

    container = MagicMock()
    container.labels = {SERVICE_LABEL: "api_gateway"}
    container.name = "api_gateway"
    container.short_id = "abc123"

    container.logs.side_effect = NotFound("container gone")

    result = _follow_container(container, store)

    assert result is None
    assert store.get(REQUEST_ID) is None


def test_follow_container_handles_generic_error():
    store = TraceStore()

    container = MagicMock()
    container.labels = {SERVICE_LABEL: "api_gateway"}
    container.name = "api_gateway"
    container.short_id = "abc123"

    container.logs.side_effect = RuntimeError("docker failed")

    result = _follow_container(container, store)

    assert result is None
    assert store.get(REQUEST_ID) is None


def test_collector_manager_initializes_docker_client(monkeypatch):
    fake_docker_client = MagicMock()
    mock_from_env = MagicMock(return_value=fake_docker_client)

    monkeypatch.setattr(
        collector.docker,
        "from_env",
        mock_from_env,
    )

    store = TraceStore()

    manager = CollectorManager(
        store=store,
        project="inmobiliaria-test",
    )

    assert manager._store is store
    assert manager._project == "inmobiliaria-test"
    assert manager._client == fake_docker_client
    assert manager._followed == set()
    assert manager._stop.is_set() is False

    mock_from_env.assert_called_once_with()


def test_collector_manager_start_starts_discovery_thread(monkeypatch):
    fake_docker_client = MagicMock()

    monkeypatch.setattr(
        collector.docker,
        "from_env",
        MagicMock(return_value=fake_docker_client),
    )

    created_threads = []

    class FakeThread:
        def __init__(self, target, name=None, daemon=None, args=()):
            self.target = target
            self.name = name
            self.daemon = daemon
            self.args = args
            self.started = False
            created_threads.append(self)

        def start(self):
            self.started = True

    monkeypatch.setattr(
        collector.threading,
        "Thread",
        FakeThread,
    )

    manager = CollectorManager(store=TraceStore())

    result = manager.start()

    assert result is None
    assert len(created_threads) == 1

    thread = created_threads[0]

    assert thread.target == manager._discover_loop
    assert thread.name == "tracer-discovery"
    assert thread.daemon is True
    assert thread.started is True
    assert manager._discovery == thread


def test_collector_manager_stop_sets_stop_event(monkeypatch):
    fake_docker_client = MagicMock()

    monkeypatch.setattr(
        collector.docker,
        "from_env",
        MagicMock(return_value=fake_docker_client),
    )

    manager = CollectorManager(store=TraceStore())

    result = manager.stop()

    assert result is None
    assert manager._stop.is_set() is True
