from unittest.mock import MagicMock

from api_gateway import main, routes
from fastapi.testclient import TestClient


def test_app_title():
    assert main.app.title == "api_gateway"


def test_health_endpoint():
    client = TestClient(main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_users_endpoint():
    client = TestClient(main.app)

    response = client.get("/users/user-123")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-123",
        "stub": "true",
    }


def test_search_endpoint_success(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-123"

    mock_publish = MagicMock()

    monkeypatch.setattr(routes.uuid, "uuid4", MagicMock(return_value=fake_uuid))
    monkeypatch.setattr(routes, "publish", mock_publish)

    client = TestClient(main.app)

    response = client.post(
        "/search",
        json={
            "prompt": "Busco piso en Salamanca con ascensor",
            "user_id": "user-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "req-123",
    }

    mock_publish.assert_called_once()

    queue_name, message = mock_publish.call_args.args

    assert queue_name == routes.settings.queue_search_requests
    assert message.request_id == "req-123"
    assert message.prompt == "Busco piso en Salamanca con ascensor"
    assert message.user_id == "user-123"


def test_search_endpoint_without_user_id(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-456"

    mock_publish = MagicMock()

    monkeypatch.setattr(routes.uuid, "uuid4", MagicMock(return_value=fake_uuid))
    monkeypatch.setattr(routes, "publish", mock_publish)

    client = TestClient(main.app)

    response = client.post(
        "/search",
        json={
            "prompt": "Busco casa con jardín",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "req-456",
    }

    _, message = mock_publish.call_args.args

    assert message.request_id == "req-456"
    assert message.prompt == "Busco casa con jardín"
    assert message.user_id is None


def test_search_endpoint_requires_prompt():
    client = TestClient(main.app)

    response = client.post(
        "/search",
        json={
            "user_id": "user-123",
        },
    )

    assert response.status_code == 422


def test_search_endpoint_propagates_publish_error(monkeypatch):
    fake_uuid = MagicMock()
    fake_uuid.__str__.return_value = "req-error"

    monkeypatch.setattr(routes.uuid, "uuid4", MagicMock(return_value=fake_uuid))
    monkeypatch.setattr(
        routes,
        "publish",
        MagicMock(side_effect=RuntimeError("SQS publish failed")),
    )

    client = TestClient(main.app, raise_server_exceptions=False)

    response = client.post(
        "/search",
        json={
            "prompt": "Busco piso",
        },
    )

    assert response.status_code == 500


def test_cors_allows_localhost_frontend():
    client = TestClient(main.app)

    response = client.options(
        "/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
