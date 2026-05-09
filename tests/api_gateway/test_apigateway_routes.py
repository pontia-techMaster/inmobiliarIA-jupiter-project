from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from api_gateway import routes
from api_gateway.routes import SearchAck, SearchBody
from pydantic import ValidationError
from shared.schemas import SearchRequest


def test_search_body_valid_with_user_id():
    body = SearchBody(
        prompt="Busco piso en Salamanca con ascensor",
        user_id="user-123",
    )

    assert body.prompt == "Busco piso en Salamanca con ascensor"
    assert body.user_id == "user-123"


def test_search_body_valid_without_user_id():
    body = SearchBody(
        prompt="Busco piso en Salamanca",
    )

    assert body.prompt == "Busco piso en Salamanca"
    assert body.user_id is None


def test_search_body_requires_prompt():
    with pytest.raises(ValidationError):
        SearchBody()


def test_search_ack_valid():
    ack = SearchAck(request_id="req-123")

    assert ack.request_id == "req-123"


def test_search_ack_requires_request_id():
    with pytest.raises(ValidationError):
        SearchAck()


def test_health_returns_ok():
    result = routes.health()

    assert result == {"status": "ok"}


def test_get_user_returns_stub():
    result = routes.get_user("user-123")

    assert result == {
        "user_id": "user-123",
        "stub": "true",
    }


def test_search_publishes_search_request(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-123"

    mock_uuid4 = MagicMock(return_value=fake_uuid)
    mock_publish = MagicMock()

    monkeypatch.setattr(routes.uuid, "uuid4", mock_uuid4)
    monkeypatch.setattr(routes, "publish", mock_publish)

    monkeypatch.setattr(
        routes,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
        ),
    )

    body = SearchBody(
        prompt="Busco piso en Salamanca con ascensor",
        user_id="user-123",
    )

    result = routes.search(body)

    assert isinstance(result, SearchAck)
    assert result.request_id == "req-123"

    mock_uuid4.assert_called_once_with()
    mock_publish.assert_called_once()

    queue_name, message = mock_publish.call_args.args

    assert queue_name == "search-requests"
    assert isinstance(message, SearchRequest)
    assert message.request_id == "req-123"
    assert message.prompt == "Busco piso en Salamanca con ascensor"
    assert message.user_id == "user-123"


def test_search_allows_user_id_none(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-456"

    mock_uuid4 = MagicMock(return_value=fake_uuid)
    mock_publish = MagicMock()

    monkeypatch.setattr(routes.uuid, "uuid4", mock_uuid4)
    monkeypatch.setattr(routes, "publish", mock_publish)

    monkeypatch.setattr(
        routes,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
        ),
    )

    body = SearchBody(
        prompt="Busco casa con jardín",
    )

    result = routes.search(body)

    assert result.request_id == "req-456"

    queue_name, message = mock_publish.call_args.args

    assert queue_name == "search-requests"
    assert isinstance(message, SearchRequest)
    assert message.request_id == "req-456"
    assert message.prompt == "Busco casa con jardín"
    assert message.user_id is None


def test_search_uses_queue_from_settings(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-789"

    mock_publish = MagicMock()

    monkeypatch.setattr(routes.uuid, "uuid4", MagicMock(return_value=fake_uuid))
    monkeypatch.setattr(routes, "publish", mock_publish)

    monkeypatch.setattr(
        routes,
        "settings",
        SimpleNamespace(
            queue_search_requests="custom-search-queue",
        ),
    )

    body = SearchBody(
        prompt="Busco ático",
    )

    routes.search(body)

    queue_name, _ = mock_publish.call_args.args

    assert queue_name == "custom-search-queue"


def test_search_propagates_publish_error(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-error"

    mock_publish = MagicMock(side_effect=RuntimeError("SQS publish failed"))

    monkeypatch.setattr(routes.uuid, "uuid4", MagicMock(return_value=fake_uuid))
    monkeypatch.setattr(routes, "publish", mock_publish)

    monkeypatch.setattr(
        routes,
        "settings",
        SimpleNamespace(
            queue_search_requests="search-requests",
        ),
    )

    body = SearchBody(
        prompt="Busco piso barato",
    )

    with pytest.raises(RuntimeError, match="SQS publish failed"):
        routes.search(body)

    mock_publish.assert_called_once()
