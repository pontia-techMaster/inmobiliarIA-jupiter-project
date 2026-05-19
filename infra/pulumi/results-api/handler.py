"""Lambda backing the read-only DynamoDB endpoints.

Routes:
  GET /results/{request_id}            — poll for a single completed search
  GET /users/{user_id}/searches        — list the user's recent search history

We dispatch on ``event["routeKey"]`` (HTTP API v2 payload format 2.0). Both
routes share this single Lambda — they read different tables but the IAM
shape and dependencies are otherwise identical.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3

ddb = boto3.client("dynamodb")

SEARCH_RESULTS_TABLE = os.environ["SEARCH_RESULTS_TABLE"]
USER_SEARCHES_TABLE = os.environ.get("USER_SEARCHES_TABLE", "")
USER_SEARCHES_LSI = "by-created-at"

_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": _CORS_HEADERS, "body": json.dumps(body)}


def _response_raw(status: int, raw_body: str) -> dict[str, Any]:
    return {"statusCode": status, "headers": _CORS_HEADERS, "body": raw_body}


# ── GET /results/{request_id} ────────────────────────────────────────────────


def _get_result(event: dict) -> dict[str, Any]:
    request_id = (event.get("pathParameters") or {}).get("request_id")
    if not request_id:
        return _response(400, {"error": "missing request_id"})

    resp = ddb.get_item(TableName=SEARCH_RESULTS_TABLE, Key={"request_id": {"S": request_id}})
    item = resp.get("Item")
    if not item:
        return _response(404, {"status": "pending", "request_id": request_id})

    return _response_raw(200, item["result"]["S"])


# ── GET /users/{user_id}/searches ────────────────────────────────────────────


def _list_searches(event: dict) -> dict[str, Any]:
    if not USER_SEARCHES_TABLE:
        return _response(500, {"error": "USER_SEARCHES_TABLE not configured"})

    user_id = (event.get("pathParameters") or {}).get("user_id")
    if not user_id:
        return _response(400, {"error": "missing user_id"})

    qs = event.get("queryStringParameters") or {}
    try:
        limit = max(1, min(int(qs.get("limit", "20")), 100))
    except (TypeError, ValueError):
        limit = 20

    resp = ddb.query(
        TableName=USER_SEARCHES_TABLE,
        IndexName=USER_SEARCHES_LSI,
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": {"S": user_id}},
        ScanIndexForward=False,
        Limit=limit,
    )

    searches = [
        {
            "user_id": it["user_id"]["S"],
            "request_id": it["request_id"]["S"],
            "created_at": int(it["created_at"]["N"]),
            "prompt": it.get("prompt", {}).get("S", ""),
            "result": json.loads(it["result"]["S"]) if "result" in it else None,
        }
        for it in resp.get("Items", [])
    ]

    return _response(200, {"user_id": user_id, "searches": searches})


def handler(event: dict, _context: object) -> dict[str, Any]:
    route_key = event.get("routeKey") or ""
    if "/users/" in route_key and route_key.endswith("/searches"):
        return _list_searches(event)
    return _get_result(event)
