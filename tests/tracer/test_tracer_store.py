from tracer.store import LogEntry, Trace, TraceStore


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


def test_add_creates_trace():
    store = TraceStore(capacity=10)
    entry = make_entry()

    store.add("req-1", entry)

    trace = store.get("req-1")

    assert isinstance(trace, Trace)
    assert trace.request_id == "req-1"
    assert trace.entries == [entry]


def test_add_appends_entry_to_existing_trace():
    store = TraceStore(capacity=10)

    entry_1 = make_entry(
        timestamp="2026-05-09T10:00:00Z",
        service="api_gateway",
        line="first log",
    )
    entry_2 = make_entry(
        timestamp="2026-05-09T10:00:01Z",
        service="vector_query",
        line="second log",
    )

    store.add("req-1", entry_1)
    store.add("req-1", entry_2)

    trace = store.get("req-1")

    assert trace is not None
    assert trace.request_id == "req-1"
    assert trace.entries == [entry_1, entry_2]


def test_get_returns_none_when_missing():
    store = TraceStore(capacity=10)

    result = store.get("missing-request-id")

    assert result is None


def test_get_returns_copy_not_internal_reference():
    store = TraceStore(capacity=10)
    entry = make_entry()

    store.add("req-1", entry)

    trace = store.get("req-1")
    assert trace is not None

    trace.entries.append(
        make_entry(
            timestamp="2026-05-09T10:00:02Z",
            service="fake_service",
            line="this should not mutate internal store",
        )
    )

    trace_again = store.get("req-1")

    assert trace_again is not None
    assert len(trace_again.entries) == 1
    assert trace_again.entries[0] == entry


def test_recent_returns_most_recent_first():
    store = TraceStore(capacity=10)

    store.add("req-1", make_entry(line="req-1"))
    store.add("req-2", make_entry(line="req-2"))
    store.add("req-3", make_entry(line="req-3"))

    recent = store.recent(limit=3)

    assert [trace.request_id for trace in recent] == [
        "req-3",
        "req-2",
        "req-1",
    ]


def test_recent_respects_limit():
    store = TraceStore(capacity=10)

    store.add("req-1", make_entry(line="req-1"))
    store.add("req-2", make_entry(line="req-2"))
    store.add("req-3", make_entry(line="req-3"))

    recent = store.recent(limit=2)

    assert [trace.request_id for trace in recent] == [
        "req-3",
        "req-2",
    ]


def test_existing_trace_is_moved_to_end_when_updated():
    store = TraceStore(capacity=10)

    store.add("req-1", make_entry(line="req-1 first"))
    store.add("req-2", make_entry(line="req-2"))
    store.add("req-1", make_entry(line="req-1 second"))

    recent = store.recent(limit=2)

    assert [trace.request_id for trace in recent] == [
        "req-1",
        "req-2",
    ]


def test_capacity_evicts_oldest_trace():
    store = TraceStore(capacity=2)

    store.add("req-1", make_entry(line="req-1"))
    store.add("req-2", make_entry(line="req-2"))
    store.add("req-3", make_entry(line="req-3"))

    assert store.get("req-1") is None
    assert store.get("req-2") is not None
    assert store.get("req-3") is not None


def test_recent_returns_copies_not_internal_references():
    store = TraceStore(capacity=10)

    store.add("req-1", make_entry(line="original"))

    recent = store.recent(limit=1)

    assert len(recent) == 1

    recent[0].entries.append(
        make_entry(
            service="fake",
            line="mutated outside",
        )
    )

    trace_again = store.get("req-1")

    assert trace_again is not None
    assert len(trace_again.entries) == 1
    assert trace_again.entries[0].line == "original"
