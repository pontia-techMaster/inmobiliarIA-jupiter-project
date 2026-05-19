from unittest.mock import MagicMock

import pytest
from ranking_and_rendering import handler
from shared.schemas import PromptField, RankJob, SearchResponse


def _field(name="price", value=None, strength="soft") -> PromptField:
    return PromptField(
        name=name,
        value=value or [200000],
        strength=strength,
        extraction_context="test context",
    )


def test_build_result_item_with_full_payload():
    doc = {
        "id": "prop-1",
        "payload": {
            "price": 180000,
            "street": "Calle Toro",
            "neighborhood": "Centro",
            "district": "Salamanca",
            "rooms": 3,
            "surface": 85,
        },
        "computed_score": 0.99,
    }

    result = handler.build_result_item(doc)

    assert result == {
        "id": "prop-1",
        "price": 180000,
        "property_type": None,
        "property_subtype": None,
        "street": "Calle Toro",
        "neighborhood": "Centro",
        "district": "Salamanca",
        "rooms": 3,
        "bathrooms": None,
        "surface": 85,
        "floor": None,
        "is_exterior": None,
        "has_elevator": None,
        "images": None,
        "url": None,
        "description": None,
        "score": 0.99,
    }


def test_build_result_item_without_payload_uses_none_values():
    doc = {
        "id": "prop-2",
        "computed_score": 0.7,
    }

    result = handler.build_result_item(doc)

    assert result == {
        "id": "prop-2",
        "price": None,
        "property_type": None,
        "property_subtype": None,
        "street": None,
        "neighborhood": None,
        "district": None,
        "rooms": None,
        "bathrooms": None,
        "surface": None,
        "floor": None,
        "is_exterior": None,
        "has_elevator": None,
        "images": None,
        "url": None,
        "description": None,
        "score": 0.7,
    }


def test_build_result_item_without_computed_score_returns_none_score():
    doc = {
        "id": "prop-3",
        "payload": {
            "price": 300000,
            "rooms": 4,
        },
    }

    result = handler.build_result_item(doc)

    assert result["id"] == "prop-3"
    assert result["price"] == 300000
    assert result["rooms"] == 4
    assert result["score"] is None


def test_handle_success(monkeypatch):
    job = RankJob(
        request_id="req-123",
        doc_ids=["prop-1", "prop-2"],
        doc_scores=[0.9, 0.7],
        fields=[_field("price", [200000], "soft")],
    )

    docs_from_qdrant = [
        {
            "id": "prop-1",
            "payload": {
                "price": 180000,
                "street": "Calle A",
                "neighborhood": "Centro",
                "district": "Salamanca",
                "rooms": 3,
                "surface": 80,
            },
        },
        {
            "id": "prop-2",
            "payload": {
                "price": 260000,
                "street": "Calle B",
                "neighborhood": "Garrido",
                "district": "Salamanca",
                "rooms": 2,
                "surface": 70,
            },
        },
    ]

    enriched_docs = [
        docs_from_qdrant[0] | {"score": 0.9},
        docs_from_qdrant[1] | {"score": 0.7},
    ]

    ranked_docs = [
        enriched_docs[0] | {"computed_score": 0.95},
        enriched_docs[1] | {"computed_score": 0.55},
    ]

    mock_get_documents = MagicMock(return_value=docs_from_qdrant)
    mock_rank = MagicMock(return_value=ranked_docs)

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    result = handler.handle(job)

    assert isinstance(result, SearchResponse)
    assert result.request_id == "req-123"
    # Spot-check the fields the test set up — extra payload slots come back as None.
    assert len(result.results) == 2
    assert result.results[0] | {} == result.results[0]  # is a plain dict
    assert {k: result.results[0][k] for k in ("id", "price", "street", "rooms", "surface", "score")} == {
        "id": "prop-1",
        "price": 180000,
        "street": "Calle A",
        "rooms": 3,
        "surface": 80,
        "score": 0.95,
    }
    assert {k: result.results[1][k] for k in ("id", "price", "street", "rooms", "surface", "score")} == {
        "id": "prop-2",
        "price": 260000,
        "street": "Calle B",
        "rooms": 2,
        "surface": 70,
        "score": 0.55,
    }

    mock_get_documents.assert_called_once_with(["prop-1", "prop-2"])
    mock_rank.assert_called_once_with(enriched_docs, job.fields)


def test_handle_with_empty_doc_ids_returns_empty_results(monkeypatch):
    job = RankJob(
        request_id="req-empty",
        doc_ids=[],
        doc_scores=[],
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
        doc_scores=[0.1, 0.2, 0.3],
        fields=[],
    )

    docs_from_qdrant = [
        {"id": "prop-1", "payload": {"price": 100000}},
        {"id": "prop-2", "payload": {"price": 200000}},
        {"id": "prop-3", "payload": {"price": 300000}},
    ]

    enriched_docs = [
        docs_from_qdrant[0] | {"score": 0.1},
        docs_from_qdrant[1] | {"score": 0.2},
        docs_from_qdrant[2] | {"score": 0.3},
    ]

    ranked_docs = [
        enriched_docs[2] | {"computed_score": 0.9},
        enriched_docs[1] | {"computed_score": 0.8},
        enriched_docs[0] | {"computed_score": 0.7},
    ]

    monkeypatch.setattr(handler, "get_documents", MagicMock(return_value=docs_from_qdrant))
    monkeypatch.setattr(handler, "rank", MagicMock(return_value=ranked_docs))

    result = handler.handle(job)

    assert [item["id"] for item in result.results] == ["prop-3", "prop-2", "prop-1"]


def test_handle_propagates_get_documents_error(monkeypatch):
    job = RankJob(
        request_id="req-error",
        doc_ids=["prop-1"],
        doc_scores=[0.8],
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
        doc_scores=[0.8],
        fields=[],
    )

    docs_from_qdrant = [{"id": "prop-1", "payload": {"price": 180000}}]
    enriched_docs = [{"id": "prop-1", "payload": {"price": 180000}, "score": 0.8}]

    mock_get_documents = MagicMock(return_value=docs_from_qdrant)
    mock_rank = MagicMock(side_effect=RuntimeError("Ranking failed"))

    monkeypatch.setattr(handler, "get_documents", mock_get_documents)
    monkeypatch.setattr(handler, "rank", mock_rank)

    with pytest.raises(RuntimeError, match="Ranking failed"):
        handler.handle(job)

    mock_get_documents.assert_called_once_with(["prop-1"])
    mock_rank.assert_called_once_with(enriched_docs, job.fields)


def test_handle_raises_when_doc_scores_length_does_not_match_docs(monkeypatch):
    job = RankJob(
        request_id="req-bad-scores",
        doc_ids=["prop-1", "prop-2"],
        doc_scores=[0.8],
        fields=[],
    )

    docs_from_qdrant = [
        {"id": "prop-1", "payload": {"price": 180000}},
        {"id": "prop-2", "payload": {"price": 200000}},
    ]

    monkeypatch.setattr(handler, "get_documents", MagicMock(return_value=docs_from_qdrant))

    with pytest.raises(ValueError):
        handler.handle(job)
