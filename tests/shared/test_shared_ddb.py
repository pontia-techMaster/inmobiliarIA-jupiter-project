"""Tests for shared.ddb — boto3 calls are mocked, no live DDB needed."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from shared import ddb


@pytest.fixture
def mock_client(monkeypatch):
    """Replace shared.ddb._client so tests never instantiate a real boto3 client."""
    client = MagicMock(name="dynamodb")
    monkeypatch.setattr(ddb, "_client", lambda: client)
    return client


@pytest.fixture
def local_settings(monkeypatch):
    """Force the helper into local mode (with an endpoint set)."""
    monkeypatch.setattr(
        ddb,
        "settings",
        SimpleNamespace(
            aws_region="eu-west-1",
            dynamodb_endpoint_url="http://dynamodb:8000",
            aws_access_key_id="x",
            aws_secret_access_key="x",
        ),
    )


@pytest.fixture
def cloud_settings(monkeypatch):
    """Force the helper into cloud mode (no endpoint override)."""
    monkeypatch.setattr(
        ddb,
        "settings",
        SimpleNamespace(
            aws_region="eu-west-1",
            dynamodb_endpoint_url="",
            aws_access_key_id="",
            aws_secret_access_key="",
        ),
    )


# ── ensure_user_searches_table ────────────────────────────────────────────────


def test_ensure_local_creates_table(mock_client, local_settings):
    ddb.ensure_user_searches_table()

    mock_client.create_table.assert_called_once()
    kwargs = mock_client.create_table.call_args.kwargs
    assert kwargs["TableName"] == ddb.USER_SEARCHES_TABLE
    # Key + LSI shape — pin the contract so a regression here is loud.
    assert [k["AttributeName"] for k in kwargs["KeySchema"]] == ["user_id", "request_id"]
    assert kwargs["LocalSecondaryIndexes"][0]["IndexName"] == "by-created-at"


def test_ensure_local_swallows_resource_in_use(mock_client, local_settings):
    err = ClientError(
        {"Error": {"Code": "ResourceInUseException", "Message": "already there"}},
        "CreateTable",
    )
    mock_client.create_table.side_effect = err

    # Should not raise — table already existing is the happy steady state.
    ddb.ensure_user_searches_table()


def test_ensure_local_reraises_unknown_client_error(mock_client, local_settings):
    err = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "nope"}},
        "CreateTable",
    )
    mock_client.create_table.side_effect = err

    with pytest.raises(ClientError):
        ddb.ensure_user_searches_table()


def test_ensure_local_warns_on_botocore_connection_error(mock_client, local_settings):
    mock_client.create_table.side_effect = EndpointConnectionError(endpoint_url="http://dynamodb:8000/")

    # Worker startup mustn't crash just because DDB Local is still warming up.
    ddb.ensure_user_searches_table()  # no raise


def test_ensure_cloud_probes_describe_table(mock_client, cloud_settings):
    ddb.ensure_user_searches_table()

    mock_client.describe_table.assert_called_once_with(TableName=ddb.USER_SEARCHES_TABLE)
    mock_client.create_table.assert_not_called()


def test_ensure_cloud_swallows_describe_failures(mock_client, cloud_settings):
    mock_client.describe_table.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}},
        "DescribeTable",
    )

    # In cloud we trust Pulumi; failure here is logged, not raised.
    ddb.ensure_user_searches_table()


# ── put_user_search ───────────────────────────────────────────────────────────


def test_put_user_search_writes_expected_item(mock_client, local_settings):
    ddb.put_user_search(
        user_id="user-1",
        request_id="req-1",
        prompt="piso en madrid",
        result={"results": [{"id": "p1"}]},
        created_at=1_700_000_000,
    )

    mock_client.put_item.assert_called_once()
    kwargs = mock_client.put_item.call_args.kwargs
    assert kwargs["TableName"] == ddb.USER_SEARCHES_TABLE
    item = kwargs["Item"]
    assert item["user_id"] == {"S": "user-1"}
    assert item["request_id"] == {"S": "req-1"}
    assert item["created_at"] == {"N": "1700000000"}
    assert item["prompt"] == {"S": "piso en madrid"}
    # `result` is round-tripped through JSON.
    assert json.loads(item["result"]["S"]) == {"results": [{"id": "p1"}]}


def test_put_user_search_defaults_created_at_to_now(mock_client, local_settings, monkeypatch):
    monkeypatch.setattr(ddb.time, "time", lambda: 1_700_000_500.7)

    ddb.put_user_search(
        user_id="user-1",
        request_id="req-1",
        prompt="x",
        result={},
    )

    item = mock_client.put_item.call_args.kwargs["Item"]
    assert item["created_at"] == {"N": "1700000500"}


# ── list_user_searches ────────────────────────────────────────────────────────


def test_list_user_searches_queries_lsi_newest_first(mock_client, local_settings):
    mock_client.query.return_value = {
        "Items": [
            {
                "user_id": {"S": "user-1"},
                "request_id": {"S": "req-2"},
                "created_at": {"N": "1700000100"},
                "prompt": {"S": "más reciente"},
                "result": {"S": '{"results":[]}'},
            },
            {
                "user_id": {"S": "user-1"},
                "request_id": {"S": "req-1"},
                "created_at": {"N": "1700000000"},
                "prompt": {"S": "más antigua"},
                "result": {"S": '{"results":[{"id":"p1"}]}'},
            },
        ]
    }

    rows = ddb.list_user_searches("user-1", limit=5)

    kwargs = mock_client.query.call_args.kwargs
    assert kwargs["IndexName"] == "by-created-at"
    assert kwargs["ScanIndexForward"] is False
    assert kwargs["Limit"] == 5
    assert kwargs["ExpressionAttributeValues"] == {":uid": {"S": "user-1"}}

    assert len(rows) == 2
    assert rows[0]["request_id"] == "req-2"
    assert rows[0]["created_at"] == 1_700_000_100
    assert rows[0]["prompt"] == "más reciente"
    assert rows[0]["result"] == {"results": []}
    assert rows[1]["result"] == {"results": [{"id": "p1"}]}


def test_list_user_searches_empty(mock_client, local_settings):
    mock_client.query.return_value = {"Items": []}
    assert ddb.list_user_searches("user-x") == []


def test_item_to_dict_handles_missing_optional_fields():
    item = {
        "user_id": {"S": "u"},
        "request_id": {"S": "r"},
        "created_at": {"N": "0"},
        # no prompt, no result
    }
    out = ddb._item_to_dict(item)
    assert out["prompt"] == ""
    assert out["result"] is None
