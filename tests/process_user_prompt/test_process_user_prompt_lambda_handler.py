"""Minimal coverage for the Lambda entrypoint.

The cold-start SSM lookup at the top of lambda_handler.py is skipped because
neither GEMINI_API_KEY nor GEMINI_API_KEY_PARAM is set in the test env. We
only exercise the ``handler()`` function, mocking the downstream ``handle``
and ``publish`` so this test doesn't talk to Gemini or SQS.
"""

import json
from unittest.mock import MagicMock

import pytest
from process_user_prompt import lambda_handler


@pytest.fixture
def mock_pipeline(monkeypatch):
    """Patch the two side-effecting collaborators of `handler()`."""
    handle = MagicMock()
    publish = MagicMock()
    monkeypatch.setattr(lambda_handler, "handle", handle)
    monkeypatch.setattr(lambda_handler, "publish", publish)
    return handle, publish


def _sqs_event(prompt: str = "piso 3 habitaciones", request_id: str = "test-id") -> dict:
    return {
        "Records": [
            {"body": json.dumps({"request_id": request_id, "prompt": prompt})},
        ]
    }


def test_handler_calls_handle_and_publishes_when_output(mock_pipeline):
    handle, publish = mock_pipeline
    sentinel_out = MagicMock()
    handle.return_value = sentinel_out

    result = lambda_handler.handler(_sqs_event(), context=None)

    assert result == {"batchItemFailures": []}
    handle.assert_called_once()
    publish.assert_called_once()
    # First positional arg to publish is the queue name.
    args, _ = publish.call_args
    assert args[1] is sentinel_out


def test_handler_skips_publish_when_handle_returns_none(mock_pipeline):
    handle, publish = mock_pipeline
    handle.return_value = None

    result = lambda_handler.handler(_sqs_event(), context=None)

    assert result == {"batchItemFailures": []}
    handle.assert_called_once()
    publish.assert_not_called()


def test_handler_processes_multiple_records(mock_pipeline):
    handle, publish = mock_pipeline
    handle.return_value = MagicMock()
    event = {
        "Records": [
            {"body": json.dumps({"request_id": "id-1", "prompt": "uno"})},
            {"body": json.dumps({"request_id": "id-2", "prompt": "dos"})},
        ]
    }

    lambda_handler.handler(event, context=None)

    assert handle.call_count == 2
    assert publish.call_count == 2


def test_handler_handles_empty_batch(mock_pipeline):
    handle, publish = mock_pipeline
    result = lambda_handler.handler({"Records": []}, context=None)
    assert result == {"batchItemFailures": []}
    handle.assert_not_called()
    publish.assert_not_called()
