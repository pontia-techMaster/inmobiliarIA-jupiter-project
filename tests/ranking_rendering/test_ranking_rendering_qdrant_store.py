from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import ranking_and_rendering.qdrant_store as qdrant_store


@pytest.fixture(autouse=True)
def reset_qdrant_client():
    qdrant_store._client = None
    yield
    qdrant_store._client = None


def test_get_client_creates_qdrant_client_with_settings_url(monkeypatch):
    fake_client = MagicMock()
    mock_qdrant_client_class = MagicMock(return_value=fake_client)

    monkeypatch.setattr(qdrant_store, "QdrantClient", mock_qdrant_client_class)
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store.get_client()

    assert result == fake_client
    mock_qdrant_client_class.assert_called_once_with(
        url="http://fake-qdrant:6333",
        api_key=None,
        check_compatibility=False,
    )


def test_get_client_reuses_existing_client(monkeypatch):
    fake_client = MagicMock()
    mock_qdrant_client_class = MagicMock(return_value=fake_client)

    monkeypatch.setattr(qdrant_store, "QdrantClient", mock_qdrant_client_class)
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    first_client = qdrant_store.get_client()
    second_client = qdrant_store.get_client()

    assert first_client == fake_client
    assert second_client == fake_client
    mock_qdrant_client_class.assert_called_once()


def test_get_documents_returns_empty_list_when_no_doc_ids(monkeypatch):
    mock_get_client = MagicMock()
    monkeypatch.setattr(qdrant_store, "get_client", mock_get_client)

    result = qdrant_store.get_documents([])

    assert result == []
    mock_get_client.assert_not_called()


def test_get_documents_calls_retrieve_with_expected_arguments(monkeypatch):
    fake_client = MagicMock()
    fake_client.retrieve.return_value = []

    monkeypatch.setattr(qdrant_store, "get_client", MagicMock(return_value=fake_client))
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    doc_ids = ["prop-1", "prop-2"]

    result = qdrant_store.get_documents(doc_ids)

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
            "price": 180000,
            "rooms": 3,
        },
    )

    point_2 = SimpleNamespace(
        id="prop-2",
        payload={
            "price": 250000,
            "rooms": 4,
        },
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point_1, point_2]

    monkeypatch.setattr(qdrant_store, "get_client", MagicMock(return_value=fake_client))
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store.get_documents(["prop-1", "prop-2"])

    assert result == [
        {
            "id": "prop-1",
            "payload": {
                "price": 180000,
                "rooms": 3,
            },
        },
        {
            "id": "prop-2",
            "payload": {
                "price": 250000,
                "rooms": 4,
            },
        },
    ]


def test_get_documents_uses_empty_payload_when_payload_is_none(monkeypatch):
    point = SimpleNamespace(
        id="prop-1",
        payload=None,
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point]

    monkeypatch.setattr(qdrant_store, "get_client", MagicMock(return_value=fake_client))
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store.get_documents(["prop-1"])

    assert result == [
        {
            "id": "prop-1",
            "payload": {},
        }
    ]


def test_get_documents_preserves_point_id_type(monkeypatch):
    point = SimpleNamespace(
        id=123,
        payload={"price": 180000},
    )

    fake_client = MagicMock()
    fake_client.retrieve.return_value = [point]

    monkeypatch.setattr(qdrant_store, "get_client", MagicMock(return_value=fake_client))
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store.get_documents(["123"])

    assert result[0]["id"] == 123
    assert result[0]["payload"] == {"price": 180000}


def test_get_documents_propagates_qdrant_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.retrieve.side_effect = RuntimeError("Qdrant retrieve failed")

    monkeypatch.setattr(qdrant_store, "get_client", MagicMock(return_value=fake_client))
    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    with pytest.raises(RuntimeError, match="Qdrant retrieve failed"):
        qdrant_store.get_documents(["prop-1"])

    fake_client.retrieve.assert_called_once_with(
        collection_name="properties",
        ids=["prop-1"],
        with_payload=True,
        with_vectors=False,
    )
