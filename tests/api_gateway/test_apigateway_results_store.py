"""Tests for api_gateway.results_store."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from api_gateway import results_store as rs
from shared.schemas import SearchResponse


def test_put_then_get_round_trips():
    s = rs.ResultsStore()
    s.put("req-1", {"results": [{"id": "p1"}]})
    assert s.get("req-1") == {"results": [{"id": "p1"}]}


def test_get_unknown_returns_none():
    s = rs.ResultsStore()
    assert s.get("missing") is None


def test_get_evicts_stale_entries(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(rs.time, "time", lambda: fake_time[0])

    s = rs.ResultsStore()
    s.put("req-1", {"ok": True})

    # Within TTL: still there.
    fake_time[0] = 1000.0 + rs._TTL_SECONDS - 1
    assert s.get("req-1") == {"ok": True}

    # Past TTL: evicted on access, future gets return None.
    fake_time[0] = 1000.0 + rs._TTL_SECONDS + 1
    assert s.get("req-1") is None
    assert s.get("req-1") is None  # idempotent — already popped


def test_put_evicts_other_stale_entries(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(rs.time, "time", lambda: fake_time[0])

    s = rs.ResultsStore()
    s.put("old", {"v": 1})
    fake_time[0] = 1000.0 + rs._TTL_SECONDS + 5
    # Putting a *new* item triggers eviction of the old one inside the lock.
    s.put("new", {"v": 2})

    assert s.get("new") == {"v": 2}
    # The fresh write reset the clock for `new`, but `old` should be gone.
    assert "old" not in s._data


# ── _consumer_loop ────────────────────────────────────────────────────────────


def test_consumer_loop_caches_messages(monkeypatch):
    """One iteration of the inner consume → cache step."""
    s = rs.ResultsStore()
    monkeypatch.setattr(rs, "store", s)

    msg = SearchResponse(request_id="req-9", results=[{"id": "x"}])

    consume_mock = MagicMock(return_value=iter([msg]))
    monkeypatch.setattr(rs, "consume", consume_mock)
    monkeypatch.setattr(
        rs,
        "settings",
        SimpleNamespace(queue_search_responses="search-responses"),
    )

    # The loop is `while True`; break out by raising on the second consume call.
    call_count = {"n": 0}

    def consume_then_break(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return iter([msg])
        raise SystemExit("stop")

    consume_mock.side_effect = consume_then_break

    # Replace time.sleep so the except branch doesn't actually wait.
    monkeypatch.setattr(rs.time, "sleep", lambda _: None)

    with pytest.raises(SystemExit):
        # Sleep was patched, but the second consume call raises SystemExit
        # directly out of the for-loop, which Exception doesn't catch.
        rs._consumer_loop()

    assert s.get("req-9") == {"request_id": "req-9", "results": [{"id": "x"}]}
    consume_mock.assert_called_with("search-responses", SearchResponse)


def test_consumer_loop_recovers_from_consume_exception(monkeypatch):
    """A transient SQS error logs + retries instead of killing the thread."""
    s = rs.ResultsStore()
    monkeypatch.setattr(rs, "store", s)
    monkeypatch.setattr(
        rs,
        "settings",
        SimpleNamespace(queue_search_responses="search-responses"),
    )

    attempts = {"n": 0}

    def flaky_consume(*_args, **_kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("sqs blip")
        # Second attempt: SystemExit is not caught by the bare-Exception
        # handler, so it exits the loop cleanly for the test.
        raise SystemExit("stop")

    monkeypatch.setattr(rs, "consume", flaky_consume)
    sleeps: list[float] = []
    monkeypatch.setattr(rs.time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(SystemExit):
        rs._consumer_loop()

    assert attempts["n"] == 2  # retried once
    assert sleeps == [2]  # slept between attempts


def test_start_consumer_spawns_daemon_thread(monkeypatch):
    started = {"called": False, "daemon": None, "name": None}

    class FakeThread:
        def __init__(self, target, name, daemon):  # noqa: D401 — stub
            started["daemon"] = daemon
            started["name"] = name

        def start(self):
            started["called"] = True

    monkeypatch.setattr(rs.threading, "Thread", FakeThread)

    rs.start_consumer()

    assert started["called"] is True
    assert started["daemon"] is True
    assert started["name"] == "search-responses-consumer"
