from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import ranking_and_rendering.qdrant_store as qdrant_client


@pytest.fixture(autouse=True)
def reset_qdrant_client():
    qdrant_client._client = None
    yield
    qdrant_client._client = None


def test_get_client_creates_qdrant_client_with_settings_url(monkeypatch):
    fake_client = MagicMock()
    mock_qdrant_client_class = MagicMock(return_value=fake_client)

    monkeypatch.setattr(
        qdrant_client,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_client.get_client()

    assert result == fake_client

    mock_qdrant_client_class.assert_called_once_with(
        url="http://fake-qdrant:6333",
        check_compatibility=False,
    )


def test_get_client_reuses_existing_client(monkeypatch):
    fake_client = MagicMock()
    mock_qdrant_client_class = MagicMock(return_value=fake_client)

    monkeypatch.setattr(
        qdrant_client,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    first_client = qdrant_client.get_client()
    second_client = qdrant_client.get_client()

    assert first_client == fake_client
    assert second_client == fake_client

    mock_qdrant_client_class.assert_called_once_with(
        url="http://fake-qdrant:6333",
        check_compatibility=False,
    )


def test_get_documents_returns_empty_list_when_no_doc_ids(monkeypatch):
    mock_get_client = MagicMock()

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        mock_get_client,
    )

    result = qdrant_client.get_documents([])

    assert result == []
    mock_get_client.assert_not_called()


def test_get_documents_calls_retrieve_with_expected_arguments(monkeypatch):
    fake_client = MagicMock()
    fake_client.retrieve.return_value = []

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    doc_ids = ["prop-1", "prop-2"]

    result = qdrant_client.get_documents(doc_ids)

    assert result == []

    fake_client.retrieve.assert_called_once_with(
        collection_name="properties",
        ids=doc_ids,
        with_payload=True,
        with_vectors=False,
    )


def test_get_documents_converts_qdrant_records_to_dicts(monkeypatch):
    point_1 = SimpleNamespace(
        id="prop-1",
        payload={
            "title": "Piso bonito",
            "price": 180000,
            "score": 0.95,
        },
    )

    point_2 = SimpleNamespace(
        id="prop-2",
        payload={
            "title": "Casa grande",
            "price": 250000,
            "score": 0.75,
        },
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point_1, point_2]

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_client.get_documents(["prop-1", "prop-2"])

    assert result == [
        {
            "id": "prop-1",
            "payload": {
                "title": "Piso bonito",
                "price": 180000,
                "score": 0.95,
            },
            "score": 0.95,
        },
        {
            "id": "prop-2",
            "payload": {
                "title": "Casa grande",
                "price": 250000,
                "score": 0.75,
            },
            "score": 0.75,
        },
    ]


def test_get_documents_uses_score_1_when_payload_has_no_score(monkeypatch):
    point = SimpleNamespace(
        id="prop-1",
        payload={
            "title": "Piso sin score",
            "price": 180000,
        },
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point]

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_client.get_documents(["prop-1"])

    assert result == [
        {
            "id": "prop-1",
            "payload": {
                "title": "Piso sin score",
                "price": 180000,
            },
            "score": 1.0,
        }
    ]


def test_get_documents_uses_empty_payload_when_payload_is_none(monkeypatch):
    point = SimpleNamespace(
        id="prop-1",
        payload=None,
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point]

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_client.get_documents(["prop-1"])

    assert result == [
        {
            "id": "prop-1",
            "payload": {},
            "score": 1.0,
        }
    ]


def test_get_documents_preserves_point_id_type(monkeypatch):
    point = SimpleNamespace(
        id=123,
        payload={
            "title": "Piso con id numérico",
            "score": 0.8,
        },
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point]

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_client.get_documents(["123"])

    assert result[0]["id"] == 123
    assert result[0]["score"] == 0.8


def test_get_documents_propagates_qdrant_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.retrieve.side_effect = RuntimeError("Qdrant retrieve failed")

    monkeypatch.setattr(
        qdrant_client,
        "get_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_client,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    with pytest.raises(RuntimeError, match="Qdrant retrieve failed"):
        qdrant_client.get_documents(["prop-1"])

    fake_client.retrieve.assert_called_once_with(
        collection_name="properties",
        ids=["prop-1"],
        with_payload=True,
        with_vectors=False,
    )
