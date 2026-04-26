from unittest.mock import patch

from ranking_and_rendering.handler import handle
from shared.schemas import RankJob


# harcode data fot teszt mock
def test_ranking_and_rendering_service():
    job = RankJob(
        request_id="test-123",
        doc_ids=["1", "2", "3"],
        filters={
            "city": "Salamanca",
            "neighborhood": "Centro",
            "district": "Centro",
            "max_price": 200000,
            "min_rooms": 3,
            "property_type": "apartment",
            "property_subtype": "flat",
            "min_surface": 80,
            "min_bathrooms": 2,
            "floor": ["1", "2", "3"],
            "is_exterior": True,
            "has_elevator": True,
        },
    )

    mock_docs = [
        {
            "id": "1",
            "score": 0.80,
            "payload": {
                "city": "Salamanca",
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
                "city": "Salamanca",
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
                "city": "Madrid",
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
    # Imprime el SearchResponse completo o solo los resultados
    print("\nResultados ordenados:")
    for result in response.results:
        print(result)  # En lugar de print(result)
