from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from data_ingestion import handler
from data_ingestion.extractor import PropertyData


@pytest.fixture
def fake_property():
    return PropertyData(
        id="123",
        idealista_id=999,
        price=150000,
        property_type="apartment",
        property_subtype="flat",
        street="Calle Mayor",
        neighborhood="Centro",
        district="Salamanca",
        surface=80,
        rooms=3,
        bathrooms=2,
        description="Descripción original que no debería ir en payload",
        floor="2",
        is_exterior=True,
        has_elevator=True,
        images=["image.webp"],
        url="https://example.com/property/123",
    )


def test_ingest_creates_collection_and_upserts(fake_property, monkeypatch):
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    mock_qdrant_client_class = MagicMock(return_value=mock_client)

    monkeypatch.setattr(
        handler,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="properties",
        ),
    )

    descriptions = ["Descripción normalizada para Qdrant"]
    embeddings = [[0.1] * handler.EMBEDDINGS_DIMENSIONALITY]

    result = handler.ingest(
        properties=[fake_property],
        descriptions=descriptions,
        embeddings=embeddings,
    )

    assert result is None

    mock_qdrant_client_class.assert_called_once_with(url="http://localhost:6333")

    mock_client.collection_exists.assert_called_once_with(collection_name="properties")

    mock_client.create_collection.assert_called_once()
    mock_client.upsert.assert_called_once()

    _, upsert_kwargs = mock_client.upsert.call_args

    assert upsert_kwargs["collection_name"] == "properties"
    assert upsert_kwargs["wait"] is True
    assert len(upsert_kwargs["points"]) == 1

    point = upsert_kwargs["points"][0]

    assert point.id == 999
    assert point.vector == embeddings[0]

    assert point.payload["price"] == 150000
    assert point.payload["property_type"] == "apartment"
    assert point.payload["property_subtype"] == "flat"
    assert point.payload["description"] == "Descripción normalizada para Qdrant"

    assert "id" not in point.payload


def test_ingest_does_not_create_collection_when_exists(
    fake_property,
    monkeypatch,
):
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    mock_qdrant_client_class = MagicMock(return_value=mock_client)

    monkeypatch.setattr(
        handler,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="properties",
        ),
    )

    descriptions = ["Descripción normalizada"]
    embeddings = [[0.1] * handler.EMBEDDINGS_DIMENSIONALITY]

    result = handler.ingest(
        properties=[fake_property],
        descriptions=descriptions,
        embeddings=embeddings,
    )

    assert result is None

    mock_client.collection_exists.assert_called_once_with(collection_name="properties")

    mock_client.create_collection.assert_not_called()
    mock_client.upsert.assert_called_once()


def test_ingest_raises_error_when_input_lengths_do_not_match(
    fake_property,
    monkeypatch,
):
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    mock_qdrant_client_class = MagicMock(return_value=mock_client)

    monkeypatch.setattr(
        handler,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="properties",
        ),
    )

    with pytest.raises(ValueError):
        handler.ingest(
            properties=[fake_property],
            descriptions=[],
            embeddings=[[0.1] * handler.EMBEDDINGS_DIMENSIONALITY],
        )

    mock_client.upsert.assert_not_called()


def test_ingest_raises_error_when_qdrant_upsert_fails(
    fake_property,
    monkeypatch,
):
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True
    mock_client.upsert.side_effect = RuntimeError("Qdrant upsert failed")

    mock_qdrant_client_class = MagicMock(return_value=mock_client)

    monkeypatch.setattr(
        handler,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="properties",
        ),
    )

    with pytest.raises(RuntimeError, match="Qdrant upsert failed"):
        handler.ingest(
            properties=[fake_property],
            descriptions=["Descripción normalizada"],
            embeddings=[[0.1] * handler.EMBEDDINGS_DIMENSIONALITY],
        )

    mock_client.upsert.assert_called_once()
