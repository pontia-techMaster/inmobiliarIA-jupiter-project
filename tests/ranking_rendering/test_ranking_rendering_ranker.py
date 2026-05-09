import sys
from unittest.mock import patch

sys.path.append("services/ranking_and_rendering/src")

# ruff: noqa: E402
from unittest.mock import MagicMock

from ranking_and_rendering import ranker
from ranking_and_rendering.handler import handle
from shared.schemas import PromptField, RankJob


def test_ranking_and_rendering_service():
    job = RankJob(
        request_id="test-123",
        doc_ids=["1", "2", "3"],
        fields=[
            PromptField(name="price", value=[200000], strength="soft", extraction_context=""),
            PromptField(name="rooms", value=[3], strength="soft", extraction_context=""),
            PromptField(name="property_type", value=["apartment", "house"], strength="soft", extraction_context=""),
            PromptField(name="is_exterior", value=[True], strength="soft", extraction_context=""),
            PromptField(name="has_elevator", value=[True], strength="soft", extraction_context=""),
        ],
    )

    mock_docs = [
        {
            "id": "1",
            "score": 0.80,
            "payload": {
                "neighborhood": "Centro",
                "district": "Centro",
                "price": 180000,
                "surface": 85,
                "rooms": 3,
                "bathrooms": 2,
                "property_type": "apartment",
                "property_subtype": "flat",
                "floor": "2",
                "is_exterior": True,
                "has_elevator": True,
            },
        },
        {
            "id": "2",
            "score": 0.90,
            "payload": {
                "neighborhood": "Garrido",
                "district": "Norte",
                "price": 220000,
                "surface": 70,
                "rooms": 2,
                "bathrooms": 1,
                "property_type": "apartment",
                "property_subtype": "flat",
                "floor": "4",
                "is_exterior": False,
                "has_elevator": True,
            },
        },
        {
            "id": "3",
            "score": 0.95,
            "payload": {
                "neighborhood": "Centro",
                "district": "Centro",
                "price": 190000,
                "surface": 90,
                "rooms": 3,
                "bathrooms": 2,
                "property_type": "house",
                "property_subtype": "chalet",
                "floor": "bajo",
                "is_exterior": True,
                "has_elevator": False,
            },
        },
    ]

    with patch("ranking_and_rendering.handler.get_documents", return_value=mock_docs):
        response = handle(job)

    assert response.request_id == "test-123"
    assert response.results[0]["id"] == "1"
    assert len(response.results) == 3


def make_field(name, value, strength="soft", context="test context"):
    return PromptField(
        name=name,
        value=value,
        strength=strength,
        extraction_context=context,
    )


def test_rank_returns_empty_list_when_no_documents():
    result = ranker.rank(
        documents=[],
        fields=[],
    )

    assert result == []


def test_rank_uses_existing_score_when_present(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {},
            "score": 0.8,
        }
    ]

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert result == [
        {
            "id": "prop-1",
            "payload": {},
            "score": 0.8,
        }
    ]


def test_rank_uses_default_score_when_missing(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {},
        }
    ]

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert result == [
        {
            "id": "prop-1",
            "payload": {},
            "score": 1.0,
        }
    ]


def test_rank_converts_score_to_float(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {},
            "score": "0.75",
        }
    ]

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert result[0]["score"] == 0.75
    assert isinstance(result[0]["score"], float)


def test_rank_sorts_documents_by_score_desc(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {},
            "score": 0.4,
        },
        {
            "id": "prop-2",
            "payload": {},
            "score": 0.9,
        },
        {
            "id": "prop-3",
            "payload": {},
            "score": 0.6,
        },
    ]

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert [doc["id"] for doc in result] == [
        "prop-2",
        "prop-3",
        "prop-1",
    ]

    assert [doc["score"] for doc in result] == [
        0.9,
        0.6,
        0.4,
    ]


def test_rank_applies_ranking_rules(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {
                "property_type": "apartment",
            },
            "score": 1.0,
        }
    ]

    fields = [
        make_field(
            name="property_type",
            value=["apartment"],
            context="piso",
        )
    ]

    rule_1 = MagicMock()
    rule_1.apply.return_value = 1.3

    rule_2 = MagicMock()
    rule_2.apply.return_value = 1.6

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [rule_1, rule_2],
    )

    result = ranker.rank(
        documents=documents,
        fields=fields,
    )

    assert result[0]["score"] == 1.6

    expected_fields_dict = {
        "property_type": fields[0],
    }

    rule_1.apply.assert_called_once_with(
        score=1.0,
        payload={"property_type": "apartment"},
        fields=expected_fields_dict,
    )

    rule_2.apply.assert_called_once_with(
        score=1.3,
        payload={"property_type": "apartment"},
        fields=expected_fields_dict,
    )


def test_rank_builds_fields_dict_by_field_name(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {
                "price": 180000,
                "rooms": 3,
            },
            "score": 1.0,
        }
    ]

    fields = [
        make_field(
            name="price",
            value=[200000],
            context="menos de 200000",
        ),
        make_field(
            name="rooms",
            value=[3],
            context="3 habitaciones",
        ),
    ]

    rule = MagicMock()
    rule.apply.return_value = 1.0

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [rule],
    )

    ranker.rank(
        documents=documents,
        fields=fields,
    )

    _, kwargs = rule.apply.call_args

    assert kwargs["fields"] == {
        "price": fields[0],
        "rooms": fields[1],
    }


def test_rank_uses_empty_payload_when_missing(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "score": 1.0,
        }
    ]

    rule = MagicMock()
    rule.apply.return_value = 1.0

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [rule],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert result == [
        {
            "id": "prop-1",
            "score": 1.0,
        }
    ]

    rule.apply.assert_called_once_with(
        score=1.0,
        payload={},
        fields={},
    )


def test_rank_does_not_mutate_original_documents(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {
                "property_type": "apartment",
            },
            "score": 1.0,
        }
    ]

    original_documents = [
        {
            "id": "prop-1",
            "payload": {
                "property_type": "apartment",
            },
            "score": 1.0,
        }
    ]

    rule = MagicMock()
    rule.apply.return_value = 1.5

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [rule],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert documents == original_documents
    assert result[0]["score"] == 1.5
    assert documents[0]["score"] == 1.0


def test_rank_orders_after_rules_are_applied(monkeypatch):
    documents = [
        {
            "id": "prop-1",
            "payload": {
                "boost": False,
            },
            "score": 1.0,
        },
        {
            "id": "prop-2",
            "payload": {
                "boost": True,
            },
            "score": 0.5,
        },
    ]

    class BoostRule:
        def apply(self, score, payload, fields):
            if payload.get("boost") is True:
                return score + 1.0
            return score

    monkeypatch.setattr(
        ranker,
        "RANKING_RULES",
        [BoostRule()],
    )

    result = ranker.rank(
        documents=documents,
        fields=[],
    )

    assert [doc["id"] for doc in result] == [
        "prop-2",
        "prop-1",
    ]

    assert result[0]["score"] == 1.5
    assert result[1]["score"] == 1.0
