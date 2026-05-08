from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from process_user_prompt import worker
from shared.schemas import ProcessUserPromptResponse, SearchRequest


def test_main_consumes_handles_and_publishes(monkeypatch):
    req = SearchRequest(
        request_id="req-123",
        prompt="Busco piso en Madrid con ascensor",
        user_id="user-1",
    )

    response = ProcessUserPromptResponse(
        request_id="req-123",
        prompt="Busco piso en Madrid con ascensor",
        fields=[
            {
                "name": "property_type",
                "value": ["apartment"],
                "strength": "soft",
                "extraction_context": "piso",
            },
            {
                "name": "location",
                "value": ["Madrid"],
                "strength": "soft",
                "extraction_context": "Madrid",
            },
            {
                "name": "has_elevator",
                "value": [True],
                "strength": "soft",
                "extraction_context": "con ascensor",
            },
        ],
        extra_info="",
    )

    mock_consume = MagicMock(return_value=[req])
    mock_handle = MagicMock(return_value=response)
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
            queue_query_jobs="query-jobs",
        ),
    )

    result = worker.main()

    assert result is None

    mock_consume.assert_called_once_with(
        "search-requests",
        SearchRequest,
    )

    mock_handle.assert_called_once_with(req)

    mock_publish.assert_called_once_with(
        "query-jobs",
        response,
    )


def test_main_without_messages_does_not_publish(monkeypatch):
    mock_consume = MagicMock(return_value=[])
    mock_handle = MagicMock()
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
            queue_query_jobs="query-jobs",
        ),
    )

    result = worker.main()

    assert result is None

    mock_consume.assert_called_once_with(
        "search-requests",
        SearchRequest,
    )

    mock_handle.assert_not_called()
    mock_publish.assert_not_called()


def test_main_processes_multiple_messages(monkeypatch):
    req_1 = SearchRequest(
        request_id="req-1",
        prompt="Busco piso en Madrid",
    )

    req_2 = SearchRequest(
        request_id="req-2",
        prompt="Busco casa con jardín",
    )

    response_1 = ProcessUserPromptResponse(
        request_id="req-1",
        prompt="Busco piso en Madrid",
        fields=[
            {
                "name": "property_type",
                "value": ["apartment"],
                "strength": "soft",
                "extraction_context": "piso",
            }
        ],
        extra_info="",
    )

    response_2 = ProcessUserPromptResponse(
        request_id="req-2",
        prompt="Busco casa con jardín",
        fields=[
            {
                "name": "property_type",
                "value": ["house"],
                "strength": "soft",
                "extraction_context": "casa",
            }
        ],
        extra_info="Vivienda con jardín.",
    )

    mock_consume = MagicMock(return_value=[req_1, req_2])
    mock_handle = MagicMock(side_effect=[response_1, response_2])
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
            queue_query_jobs="query-jobs",
        ),
    )

    result = worker.main()

    assert result is None

    assert mock_handle.call_count == 2
    mock_handle.assert_any_call(req_1)
    mock_handle.assert_any_call(req_2)

    assert mock_publish.call_count == 2
    mock_publish.assert_any_call("query-jobs", response_1)
    mock_publish.assert_any_call("query-jobs", response_2)


def test_main_propagates_handle_error(monkeypatch):
    req = SearchRequest(
        request_id="req-error",
        prompt="Prompt que provoca error",
    )

    mock_consume = MagicMock(return_value=[req])
    mock_handle = MagicMock(
        side_effect=RuntimeError("Handler failed")
    )
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
            queue_query_jobs="query-jobs",
        ),
    )

    with pytest.raises(RuntimeError, match="Handler failed"):
        worker.main()

    mock_handle.assert_called_once_with(req)
    mock_publish.assert_not_called()


def test_main_propagates_publish_error(monkeypatch):
    req = SearchRequest(
        request_id="req-123",
        prompt="Busco piso en Madrid",
    )

    response = ProcessUserPromptResponse(
        request_id="req-123",
        prompt="Busco piso en Madrid",
        fields=[
            {
                "name": "property_type",
                "value": ["apartment"],
                "strength": "soft",
                "extraction_context": "piso",
            }
        ],
        extra_info="",
    )

    mock_consume = MagicMock(return_value=[req])
    mock_handle = MagicMock(return_value=response)
    mock_publish = MagicMock(
        side_effect=RuntimeError("Publish failed")
    )

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
            queue_query_jobs="query-jobs",
        ),
    )

    with pytest.raises(RuntimeError, match="Publish failed"):
        worker.main()

    mock_handle.assert_called_once_with(req)
    mock_publish.assert_called_once_with("query-jobs", response)