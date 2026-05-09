from unittest.mock import MagicMock

import pytest
from ranking_and_rendering import handler
from shared.schemas import RankJob, SearchResponse


def test_build_result_item_with_full_payload():
    doc = {
        "id": "prop-1",
        "payload": {
            "title": "Piso bonito en Salamanca",
            "price": 180000,
            "city": "Salamanca",
            "rooms": 3,
        },
        "score": 1.25,
    }

    result = handler.build_result_item(doc)

    assert result == {
        "id": "prop-1",
        "title": "Piso bonito en Salamanca",
        "price": 180000,
        "city": "Salamanca",
        "rooms": 3,
        "score": 1.25,
    }


def test_build_result_item_without_title_uses_default_title():
    doc = {
        "id": "prop-2",
        "payload": {
            "price": 220000,
            "city": "Madrid",
            "rooms": 2,
        },
        "score": 0.95,
    }

    result = handler.build_result_item(doc)

    assert result == {
        "id": "prop-2",
        "title": "Propiedad prop-2",
        "price": 220000,
        "city": "Madrid",
        "rooms": 2,
        "score": 0.95,
    }


def test_build_result_item_without_payload_uses_defaults():
    doc = {
        "id": "prop-3",
        "score": 0.7,
    }

    result = handler.build_result_item(doc)

    assert result == {
        "id": "prop-3",
        "title": "Propiedad prop-3",
        "price": None,
        "city": None,
        "rooms": None,
        "score": 0.7,
    }


def test_build_result_item_without_score_returns_score_none():
    doc = {
        "id": "prop-4",
        "payload": {
            "title": "Casa sin score",
            "price": 300000,
            "city": "Salamanca",
            "rooms": 4,
        },
    }

    result = handler.build_result_item(doc)

    assert result == {
        "id": "prop-4",
        "title": "Casa sin score",
        "price": 300000,
        "city": "Salamanca",
        "rooms": 4,
        "score": None,
    }


def test_handle_success(monkeypatch):
    job = RankJob(
        request_id="req-123",
        doc_ids=["prop-1", "prop-2"],
        fields=[
            {
                "name": "price",
                "value": [200000],
                "strength": "soft",
                "extraction_context": "menos de 200000 euros",
            },
            {
                "name": "property_type",
                "value": ["apartment"],
                "strength": "soft",
                "extraction_context": "piso",
            },
        ],
    )

    docs_from_qdrant = [
        {
            "id": "prop-1",
            "payload": {
                "title": "Piso barato",
                "price": 180000,
                "city": "Salamanca",
                "rooms": 3,
            },
            "score": 1.0,
        },
        {
            "id": "prop-2",
            "payload": {
                "title": "Casa cara",
                "price": 260000,
                "city": "Salamanca",
                "rooms": 4,
            },
            "score": 0.8,
        },
    ]

    ranked_docs = [
        {
            "id": "prop-1",
            "payload": {
                "title": "Piso barato",
                "price": 180000,
                "city": "Salamanca",
                "rooms": 3,
            },
            "score": 1.3,
        },
        {
            "id": "prop-2",
            "payload": {
                "title": "Casa cara",
                "price": 260000,
                "city": "Salamanca",
                "rooms": 4,
            },
            "score": 0.5,
        },
    ]

    mock_get_documents = MagicMock(return_value=docs_from_qdrant)
    mock_rank = MagicMock(return_value=ranked_docs)

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    result = handler.handle(job)

    assert isinstance(result, SearchResponse)
    assert result.request_id == "req-123"
    assert result.results == [
        {
            "id": "prop-1",
            "title": "Piso barato",
            "price": 180000,
            "city": "Salamanca",
            "rooms": 3,
            "score": 1.3,
        },
        {
            "id": "prop-2",
            "title": "Casa cara",
            "price": 260000,
            "city": "Salamanca",
            "rooms": 4,
            "score": 0.5,
        },
    ]

    mock_get_documents.assert_called_once_with(["prop-1", "prop-2"])
    mock_rank.assert_called_once_with(docs_from_qdrant, job.fields)


def test_handle_with_empty_doc_ids_returns_empty_results(monkeypatch):
    job = RankJob(
        request_id="req-empty",
        doc_ids=[],
        fields=[],
    )

    mock_get_documents = MagicMock(return_value=[])
    mock_rank = MagicMock(return_value=[])

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    result = handler.handle(job)

    assert isinstance(result, SearchResponse)
    assert result.request_id == "req-empty"
    assert result.results == []

    mock_get_documents.assert_called_once_with([])
    mock_rank.assert_called_once_with([], [])


def test_handle_preserves_ranked_order(monkeypatch):
    job = RankJob(
        request_id="req-order",
        doc_ids=["prop-1", "prop-2", "prop-3"],
        fields=[],
    )

    docs_from_qdrant = [
        {
            "id": "prop-1",
            "payload": {"title": "Primera"},
            "score": 0.1,
        },
        {
            "id": "prop-2",
            "payload": {"title": "Segunda"},
            "score": 0.2,
        },
        {
            "id": "prop-3",
            "payload": {"title": "Tercera"},
            "score": 0.3,
        },
    ]

    ranked_docs = [
        {
            "id": "prop-3",
            "payload": {"title": "Tercera"},
            "score": 0.3,
        },
        {
            "id": "prop-2",
            "payload": {"title": "Segunda"},
            "score": 0.2,
        },
        {
            "id": "prop-1",
            "payload": {"title": "Primera"},
            "score": 0.1,
        },
    ]

    mock_get_documents = MagicMock(return_value=docs_from_qdrant)
    mock_rank = MagicMock(return_value=ranked_docs)

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    result = handler.handle(job)

    assert [item["id"] for item in result.results] == [
        "prop-3",
        "prop-2",
        "prop-1",
    ]

    mock_get_documents.assert_called_once_with(["prop-1", "prop-2", "prop-3"])
    mock_rank.assert_called_once_with(docs_from_qdrant, job.fields)


def test_handle_propagates_get_documents_error(monkeypatch):
    job = RankJob(
        request_id="req-error",
        doc_ids=["prop-1"],
        fields=[],
    )

    mock_get_documents = MagicMock(side_effect=RuntimeError("Qdrant retrieval failed"))
    mock_rank = MagicMock()

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    with pytest.raises(RuntimeError, match="Qdrant retrieval failed"):
        handler.handle(job)

    mock_get_documents.assert_called_once_with(["prop-1"])
    mock_rank.assert_not_called()


def test_handle_propagates_rank_error(monkeypatch):
    job = RankJob(
        request_id="req-rank-error",
        doc_ids=["prop-1"],
        fields=[],
    )

    docs_from_qdrant = [
        {
            "id": "prop-1",
            "payload": {"title": "Piso"},
            "score": 1.0,
        }
    ]

    mock_get_documents = MagicMock(return_value=docs_from_qdrant)
    mock_rank = MagicMock(side_effect=RuntimeError("Ranking failed"))

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    with pytest.raises(RuntimeError, match="Ranking failed"):
        handler.handle(job)

    mock_get_documents.assert_called_once_with(["prop-1"])
    mock_rank.assert_called_once_with(docs_from_qdrant, job.fields)


def test_handle_propagates_build_result_item_error(monkeypatch):
    job = RankJob(
        request_id="req-build-error",
        doc_ids=["prop-1"],
        fields=[],
    )

    docs_from_qdrant = [
        {
            "payload": {"title": "Documento sin id"},
            "score": 1.0,
        }
    ]

    mock_get_documents = MagicMock(return_value=docs_from_qdrant)
    mock_rank = MagicMock(return_value=docs_from_qdrant)

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    with pytest.raises(KeyError):
        handler.handle(job)

    mock_get_documents.assert_called_once_with(["prop-1"])
    mock_rank.assert_called_once_with(docs_from_qdrant, job.fields)
