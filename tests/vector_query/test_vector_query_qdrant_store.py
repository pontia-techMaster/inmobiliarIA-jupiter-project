from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from vector_query import qdrant_store


@pytest.fixture(autouse=True)
def clear_qdrant_client_cache():
    qdrant_store._client.cache_clear()
    yield
    qdrant_store._client.cache_clear()


def test_client_creates_qdrant_client_with_settings_url(monkeypatch):
    mock_qdrant_client_class = MagicMock()
    fake_client = MagicMock()

    mock_qdrant_client_class.return_value = fake_client

    monkeypatch.setattr(
        qdrant_store,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store._client()

    assert result == fake_client

    mock_qdrant_client_class.assert_called_once_with(url="http://fake-qdrant:6333")


def test_client_is_cached(monkeypatch):
    mock_qdrant_client_class = MagicMock()
    fake_client = MagicMock()

    mock_qdrant_client_class.return_value = fake_client

    monkeypatch.setattr(
        qdrant_store,
        "QdrantClient",
        mock_qdrant_client_class,
    )

    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    first_client = qdrant_store._client()
    second_client = qdrant_store._client()

    assert first_client == fake_client
    assert second_client == fake_client

    mock_qdrant_client_class.assert_called_once_with(url="http://fake-qdrant:6333")


def test_search_calls_query_points_with_expected_arguments(monkeypatch):
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.points = []

    fake_client.query_points.return_value = fake_response

    mock_client_factory = MagicMock(return_value=fake_client)

    monkeypatch.setattr(
        qdrant_store,
        "_client",
        mock_client_factory,
    )

    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    vector = [0.1, 0.2, 0.3]
    qfilter = MagicMock()
    k = 10

    result = qdrant_store.search(
        vector=vector,
        qfilter=qfilter,
        k=k,
    )

    assert result == []

    fake_client.query_points.assert_called_once_with(
        collection_name="properties",
        query=vector,
        query_filter=qfilter,
        limit=10,
        with_payload=False,
    )


def test_search_returns_id_score_tuples(monkeypatch):
    hit_1 = SimpleNamespace(id=123, score=0.98)
    hit_2 = SimpleNamespace(id="abc", score=0.91)

    fake_response = SimpleNamespace(points=[hit_1, hit_2])

    fake_client = MagicMock()
    fake_client.query_points.return_value = fake_response

    monkeypatch.setattr(
        qdrant_store,
        "_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store.search(
        vector=[0.1, 0.2, 0.3],
        qfilter=None,
        k=2,
    )

    assert result == [
        ("123", 0.98),
        ("abc", 0.91),
    ]


def test_search_returns_empty_list_when_no_hits(monkeypatch):
    fake_response = SimpleNamespace(points=[])

    fake_client = MagicMock()
    fake_client.query_points.return_value = fake_response

    monkeypatch.setattr(
        qdrant_store,
        "_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    result = qdrant_store.search(
        vector=[0.1, 0.2, 0.3],
        qfilter=None,
        k=10,
    )

    assert result == []


def test_search_propagates_qdrant_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.query_points.side_effect = RuntimeError("Qdrant failed")

    monkeypatch.setattr(
        qdrant_store,
        "_client",
        MagicMock(return_value=fake_client),
    )

    monkeypatch.setattr(
        qdrant_store,
        "settings",
        SimpleNamespace(
            qdrant_url="http://fake-qdrant:6333",
            qdrant_collection_name="properties",
        ),
    )

    with pytest.raises(RuntimeError, match="Qdrant failed"):
        qdrant_store.search(
            vector=[0.1, 0.2, 0.3],
            qfilter=None,
            k=10,
        )
