"""HTTP routes.

``POST /search`` accepts a natural-language prompt, publishes a SearchRequest
onto ``search-requests``, and returns the ``request_id``. If the client
supplied an id (the FE does, so it can match its polling/tracing UI to the
backend chain), we honor it; otherwise we mint one.

``GET /results/{request_id}`` returns the final ``SearchResponse`` once a
background consumer has cached it from ``search-responses``. Pending requests
get ``404`` so the FE can keep polling.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from shared.ddb import list_user_searches
from shared.schemas import SearchRequest
from shared.settings import settings
from shared.sqs import publish

from api_gateway.results_store import store

log = logging.getLogger("api_gateway.routes")

router = APIRouter()


class SearchBody(BaseModel):
    prompt: str
    user_id: str | None = None
    request_id: str | None = None


class SearchAck(BaseModel):
    request_id: str


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/search", response_model=SearchAck)
def search(body: SearchBody) -> SearchAck:
    request_id = body.request_id or str(uuid.uuid4())
    log.info("POST /search request_id=%s prompt=%r", request_id, body.prompt)
    publish(
        settings.queue_search_requests,
        SearchRequest(request_id=request_id, prompt=body.prompt, user_id=body.user_id),
    )
    return SearchAck(request_id=request_id)


@router.get("/results/{request_id}")
def get_results(request_id: str) -> dict:
    payload = store.get(request_id)
    if payload is None:
        # Not ready yet (or expired) — FE keeps polling on 404.
        raise HTTPException(status_code=404, detail="pending")
    return payload


@router.get("/users/{user_id}")
def get_user(user_id: str) -> dict[str, str]:
    return {"user_id": user_id, "stub": "true"}


@router.get("/users/{user_id}/searches")
def list_searches(user_id: str, limit: int = 20) -> dict:
    """Return the user's most recent searches (newest first)."""
    try:
        items = list_user_searches(user_id, limit=limit)
    except Exception as exc:
        log.exception("list_user_searches failed for %s", user_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"user_id": user_id, "searches": items}
