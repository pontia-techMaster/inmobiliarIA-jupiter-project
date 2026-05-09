from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from shared.schemas import ProcessUserPromptResponse, RankJob
from vector_query import handler


@pytest.fixture
def query_job():
    return ProcessUserPromptResponse(
        request_id="req-123",
        prompt="Busco piso en Madrid con ascensor por menos de 200000 euros",
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
            {
                "name": "price",
                "value": [200000],
                "strength": "soft",
                "extraction_context": "menos de 200000 euros",
            },
        ],
        extra_info="",
    )


def test_handle_success(query_job, monkeypatch):
    fake_vector = [0.1, 0.2, 0.3]
    fake_filter = MagicMock()
    fake_filter.model_dump_json.return_value = '{"must": []}'
    fake_hits = [
        ("prop-1", 0.98),
        ("prop-2", 0.91),
    ]

    mock_embed_query = MagicMock(return_value=fake_vector)
    mock_build_filter = MagicMock(return_value=fake_filter)
    mock_search = MagicMock(return_value=fake_hits)

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=10),
    )

    result = handler.handle(query_job)

    assert isinstance(result, RankJob)
    assert result.request_id == "req-123"
    assert result.doc_ids == ["prop-1", "prop-2"]
    assert result.fields == query_job.fields

    mock_embed_query.assert_called_once_with(query_job.prompt)
    mock_build_filter.assert_called_once_with(query_job.fields)
    mock_search.assert_called_once_with(
        fake_vector,
        fake_filter,
        k=10,
    )


def test_handle_without_hits_returns_empty_doc_ids(query_job, monkeypatch):
    fake_vector = [0.1, 0.2, 0.3]
    fake_filter = MagicMock()
    fake_filter.model_dump_json.return_value = '{"must": []}'

    mock_embed_query = MagicMock(return_value=fake_vector)
    mock_build_filter = MagicMock(return_value=fake_filter)
    mock_search = MagicMock(return_value=[])

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=10),
    )

    result = handler.handle(query_job)

    assert isinstance(result, RankJob)
    assert result.request_id == "req-123"
    assert result.doc_ids == []
    assert result.fields == query_job.fields

    mock_embed_query.assert_called_once_with(query_job.prompt)
    mock_build_filter.assert_called_once_with(query_job.fields)
    mock_search.assert_called_once_with(
        fake_vector,
        fake_filter,
        k=10,
    )


def test_handle_uses_top_k_from_settings(query_job, monkeypatch):
    fake_vector = [0.1, 0.2, 0.3]
    fake_filter = MagicMock()
    fake_filter.model_dump_json.return_value = '{"must": []}'

    mock_embed_query = MagicMock(return_value=fake_vector)
    mock_build_filter = MagicMock(return_value=fake_filter)
    mock_search = MagicMock(return_value=[("prop-1", 0.99)])

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=25),
    )

    result = handler.handle(query_job)

    assert result.doc_ids == ["prop-1"]

    mock_search.assert_called_once_with(
        fake_vector,
        fake_filter,
        k=25,
    )


def test_handle_raises_error_when_filter_is_none(query_job, monkeypatch):
    fake_vector = [0.1, 0.2, 0.3]
    fake_hits = [("prop-1", 0.95)]

    mock_embed_query = MagicMock(return_value=fake_vector)
    mock_build_filter = MagicMock(return_value=None)
    mock_search = MagicMock(return_value=fake_hits)

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=10),
    )

    with pytest.raises(AttributeError):
        handler.handle(query_job)

    mock_embed_query.assert_called_once_with(query_job.prompt)
    mock_build_filter.assert_called_once_with(query_job.fields)
    mock_search.assert_called_once_with(
        fake_vector,
        None,
        k=10,
    )


def test_handle_propagates_embed_query_error(query_job, monkeypatch):
    mock_embed_query = MagicMock(side_effect=RuntimeError("Embedding failed"))
    mock_build_filter = MagicMock()
    mock_search = MagicMock()

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=10),
    )

    with pytest.raises(RuntimeError, match="Embedding failed"):
        handler.handle(query_job)

    mock_embed_query.assert_called_once_with(query_job.prompt)
    mock_build_filter.assert_not_called()
    mock_search.assert_not_called()


def test_handle_propagates_build_filter_error(query_job, monkeypatch):
    fake_vector = [0.1, 0.2, 0.3]

    mock_embed_query = MagicMock(return_value=fake_vector)
    mock_build_filter = MagicMock(side_effect=RuntimeError("Filter build failed"))
    mock_search = MagicMock()

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=10),
    )

    with pytest.raises(RuntimeError, match="Filter build failed"):
        handler.handle(query_job)

    mock_embed_query.assert_called_once_with(query_job.prompt)
    mock_build_filter.assert_called_once_with(query_job.fields)
    mock_search.assert_not_called()


def test_handle_propagates_search_error(query_job, monkeypatch):
    fake_vector = [0.1, 0.2, 0.3]
    fake_filter = MagicMock()
    fake_filter.model_dump_json.return_value = '{"must": []}'

    mock_embed_query = MagicMock(return_value=fake_vector)
    mock_build_filter = MagicMock(return_value=fake_filter)
    mock_search = MagicMock(side_effect=RuntimeError("Qdrant search failed"))

    monkeypatch.setattr(handler, "embed_query", mock_embed_query)
    monkeypatch.setattr(handler, "build_filter", mock_build_filter)
    monkeypatch.setattr(handler, "search", mock_search)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(qdrant_top_k=10),
    )

    with pytest.raises(RuntimeError, match="Qdrant search failed"):
        handler.handle(query_job)

    mock_embed_query.assert_called_once_with(query_job.prompt)
    mock_build_filter.assert_called_once_with(query_job.fields)
    mock_search.assert_called_once_with(
        fake_vector,
        fake_filter,
        k=10,
    )
