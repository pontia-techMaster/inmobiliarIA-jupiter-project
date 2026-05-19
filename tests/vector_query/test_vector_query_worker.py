from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from shared.schemas import ProcessUserPromptResponse, RankJob
from vector_query import worker


def test_main_consumes_handles_and_publishes(monkeypatch):
    job = ProcessUserPromptResponse(
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
                "extraction_context": "ascensor",
            },
        ],
        extra_info="",
    )

    rank_job = RankJob(
        request_id="req-123",
        doc_ids=["prop-1", "prop-2"],
        doc_scores=[0.77, 0.69],
        fields=job.fields,
    )

    mock_consume = MagicMock(return_value=[job])
    mock_handle = MagicMock(return_value=rank_job)
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_query_jobs="query-jobs",
            queue_rank_jobs="rank-jobs",
        ),
    )

    result = worker.main()

    assert result is None

    mock_consume.assert_called_once_with(
        "query-jobs",
        ProcessUserPromptResponse,
    )

    mock_handle.assert_called_once_with(job)

    mock_publish.assert_called_once_with(
        "rank-jobs",
        rank_job,
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
            queue_query_jobs="query-jobs",
            queue_rank_jobs="rank-jobs",
        ),
    )

    result = worker.main()

    assert result is None

    mock_consume.assert_called_once_with(
        "query-jobs",
        ProcessUserPromptResponse,
    )

    mock_handle.assert_not_called()
    mock_publish.assert_not_called()


def test_main_processes_multiple_jobs(monkeypatch):
    job_1 = ProcessUserPromptResponse(
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

    job_2 = ProcessUserPromptResponse(
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

    rank_job_1 = RankJob(
        request_id="req-1",
        doc_ids=["prop-1"],
        doc_scores=[0.77],
        fields=job_1.fields,
    )

    rank_job_2 = RankJob(
        request_id="req-2",
        doc_ids=["prop-2", "prop-3"],
        doc_scores=[0.78, 0.97],
        fields=job_2.fields,
    )

    mock_consume = MagicMock(return_value=[job_1, job_2])
    mock_handle = MagicMock(side_effect=[rank_job_1, rank_job_2])
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_query_jobs="query-jobs",
            queue_rank_jobs="rank-jobs",
        ),
    )

    result = worker.main()

    assert result is None

    mock_consume.assert_called_once_with(
        "query-jobs",
        ProcessUserPromptResponse,
    )

    assert mock_handle.call_count == 2
    mock_handle.assert_any_call(job_1)
    mock_handle.assert_any_call(job_2)

    assert mock_publish.call_count == 2
    mock_publish.assert_any_call("rank-jobs", rank_job_1)
    mock_publish.assert_any_call("rank-jobs", rank_job_2)


def test_main_propagates_handle_error(monkeypatch):
    job = ProcessUserPromptResponse(
        request_id="req-error",
        prompt="Prompt que provoca error",
        fields=[],
        extra_info="",
    )

    mock_consume = MagicMock(return_value=[job])
    mock_handle = MagicMock(side_effect=RuntimeError("Handler failed"))
    mock_publish = MagicMock()

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_query_jobs="query-jobs",
            queue_rank_jobs="rank-jobs",
        ),
    )

    with pytest.raises(RuntimeError, match="Handler failed"):
        worker.main()

    mock_consume.assert_called_once_with(
        "query-jobs",
        ProcessUserPromptResponse,
    )

    mock_handle.assert_called_once_with(job)
    mock_publish.assert_not_called()


def test_main_propagates_publish_error(monkeypatch):
    job = ProcessUserPromptResponse(
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

    rank_job = RankJob(
        request_id="req-123",
        doc_ids=["prop-1"],
        doc_scores=[0.77],
        fields=job.fields,
    )

    mock_consume = MagicMock(return_value=[job])
    mock_handle = MagicMock(return_value=rank_job)
    mock_publish = MagicMock(side_effect=RuntimeError("Publish failed"))

    monkeypatch.setattr(worker, "consume", mock_consume)
    monkeypatch.setattr(worker, "handle", mock_handle)
    monkeypatch.setattr(worker, "publish", mock_publish)

    monkeypatch.setattr(
        worker,
        "settings",
        SimpleNamespace(
            queue_query_jobs="query-jobs",
            queue_rank_jobs="rank-jobs",
        ),
    )

    with pytest.raises(RuntimeError, match="Publish failed"):
        worker.main()

    mock_handle.assert_called_once_with(job)
    mock_publish.assert_called_once_with("rank-jobs", rank_job)
