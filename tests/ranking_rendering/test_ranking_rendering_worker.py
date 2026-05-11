from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import ranking_and_rendering.worker as worker
from shared.schemas import RankJob, SearchResponse


def test_main_consumes_handles_and_publishes(monkeypatch):
    job = RankJob(
        request_id="req-1",
        doc_ids=["prop-1"],
        doc_scores=[0.8],
        fields=[],
    )

    response = SearchResponse(
        request_id="req-1",
        results=[{"id": "prop-1", "score": 0.9}],
    )

    mock_consume = MagicMock(return_value=iter([job]))
    mock_handle = MagicMock(return_value=response)
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)
    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_rank_jobs="rank-jobs",
            queue_search_responses="search-responses",
        ),
    )

    worker.main()

    mock_consume.assert_called_once_with("rank-jobs", RankJob)
    mock_handle.assert_called_once_with(job)
    mock_publish.assert_called_once_with("search-responses", response)


def test_main_without_messages_does_not_publish(monkeypatch):
    mock_consume = MagicMock(return_value=iter([]))
    mock_handle = MagicMock()
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)
    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_rank_jobs="rank-jobs",
            queue_search_responses="search-responses",
        ),
    )

    worker.main()

    mock_consume.assert_called_once_with("rank-jobs", RankJob)
    mock_handle.assert_not_called()
    mock_publish.assert_not_called()


def test_main_propagates_handle_error(monkeypatch):
    job = RankJob(
        request_id="req-error",
        doc_ids=["prop-1"],
        doc_scores=[0.8],
        fields=[],
    )

    mock_consume = MagicMock(return_value=iter([job]))
    mock_handle = MagicMock(side_effect=RuntimeError("handler failed"))
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)
    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_rank_jobs="rank-jobs",
            queue_search_responses="search-responses",
        ),
    )

    with pytest.raises(RuntimeError, match="handler failed"):
        worker.main()

    mock_publish.assert_not_called()
