"""DynamoDB helpers for the ``user-searches`` history table.

Same boto3 client semantics as ``shared.sqs``: respects
``DYNAMODB_ENDPOINT_URL`` (set in docker-compose for the local DDB
container) and falls back to the regional endpoint when unset (Lambda).

Schema
------
- ``user_id`` (S, partition key)
- ``request_id`` (S, sort key)
- ``created_at`` (N, epoch seconds — also the LSI sort key)
- ``prompt`` (S)
- ``result`` (S, JSON-encoded ``SearchResponse``)

LSI ``by-created-at`` gives us "list this user's searches newest first"
without a scan. GetItem(user_id, request_id) handles single-row lookups.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from shared.settings import settings

log = logging.getLogger("shared.ddb")

USER_SEARCHES_TABLE = os.environ.get("USER_SEARCHES_TABLE", "user-searches")
LSI_NAME = "by-created-at"

# Tight bounds so a slow/unreachable local DDB fails fast instead of hanging
# the worker for minutes on boto3's default retry chain. In cloud we use
# default boto3 timeouts (no custom Config) so the Lambda gets normal retries.
_LOCAL_BOTO_CONFIG = Config(
    connect_timeout=2,
    read_timeout=5,
    retries={"max_attempts": 2, "mode": "standard"},
)


def _client():
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        kwargs["config"] = _LOCAL_BOTO_CONFIG
    return boto3.client("dynamodb", **kwargs)


def ensure_user_searches_table() -> None:
    """Idempotently create the local user-searches table.

    No-op in cloud: the table is created by Pulumi, and the IAM role on
    the Lambda doesn't have ``dynamodb:CreateTable`` anyway — the call
    would throw ``AccessDeniedException``. We only attempt creation when
    a local DDB endpoint is set; otherwise we just probe with
    ``DescribeTable`` to fail fast if misconfigured.
    """
    client = _client()
    if not settings.dynamodb_endpoint_url:
        # Cloud: trust Pulumi. Probe so a misconfigured env vars surfaces early.
        try:
            client.describe_table(TableName=USER_SEARCHES_TABLE)
            log.info("user-searches table %s present", USER_SEARCHES_TABLE)
        except ClientError as exc:
            log.warning("describe_table(%s) failed: %s", USER_SEARCHES_TABLE, exc)
        return

    try:
        client.create_table(
            TableName=USER_SEARCHES_TABLE,
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "request_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "request_id", "KeyType": "RANGE"},
            ],
            LocalSecondaryIndexes=[
                {
                    "IndexName": LSI_NAME,
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        log.info("created user-searches table %s", USER_SEARCHES_TABLE)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceInUseException":
            log.debug("user-searches table %s already exists", USER_SEARCHES_TABLE)
        else:
            raise
    except BotoCoreError as exc:
        # Connection refused / timeouts to a not-yet-ready local DDB end up
        # here. Don't crash callers — they catch this anyway, but logging
        # turns the failure into a one-liner instead of a full stack.
        log.warning("ensure_user_searches_table: %s (continuing without it)", exc)


def put_user_search(
    *,
    user_id: str,
    request_id: str,
    prompt: str,
    result: dict[str, Any],
    created_at: int | None = None,
) -> None:
    client = _client()
    client.put_item(
        TableName=USER_SEARCHES_TABLE,
        Item={
            "user_id": {"S": user_id},
            "request_id": {"S": request_id},
            "created_at": {"N": str(created_at or int(time.time()))},
            "prompt": {"S": prompt},
            "result": {"S": json.dumps(result, separators=(",", ":"))},
        },
    )


def list_user_searches(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return the user's most recent searches (newest first) as plain dicts."""
    client = _client()
    resp = client.query(
        TableName=USER_SEARCHES_TABLE,
        IndexName=LSI_NAME,
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": {"S": user_id}},
        ScanIndexForward=False,  # newest first
        Limit=limit,
    )
    return [_item_to_dict(it) for it in resp.get("Items", [])]


def _item_to_dict(item: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Convert a DDB Item (AttributeValue map) to our flat external shape."""
    return {
        "user_id": item["user_id"]["S"],
        "request_id": item["request_id"]["S"],
        "created_at": int(item["created_at"]["N"]),
        "prompt": item.get("prompt", {}).get("S", ""),
        "result": json.loads(item["result"]["S"]) if "result" in item else None,
    }
