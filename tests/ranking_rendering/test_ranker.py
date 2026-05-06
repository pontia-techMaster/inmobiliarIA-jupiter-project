import sys
from unittest.mock import patch

sys.path.append("services/ranking_and_rendering/src")

# ruff: noqa: E402
from ranking_and_rendering.handler import handle
from shared.schemas import PromptField, RankJob


# harcode data fot teszt mock
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
