"""HTTP routes.

``POST /search`` accepts a natural-language prompt, publishes a SearchRequest
onto ``search-requests``, and returns a newly minted ``request_id``. The
actual search happens asynchronously down the SQS chain; the caller will
later consume the matching response from ``search-responses``.

``GET /users/{user_id}`` is a stub. Real DynamoDB access will live in
``api_gateway.ddb_client`` and eventually move into its own microservice.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from shared.schemas import SearchRequest
from shared.settings import settings
from shared.sqs import publish

log = logging.getLogger("api_gateway.routes")

router = APIRouter()


class SearchBody(BaseModel):
    prompt: str
    user_id: str | None = None


class SearchAck(BaseModel):
    request_id: str


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/search", response_model=SearchAck)
def search(body: SearchBody) -> SearchAck:
    request_id = str(uuid.uuid4())
    log.info("POST /search request_id=%s prompt=%r", request_id, body.prompt)
    publish(
        settings.queue_search_requests,
        SearchRequest(request_id=request_id, prompt=body.prompt, user_id=body.user_id),
    )
    return SearchAck(request_id=request_id)


@router.get("/users/{user_id}")
def get_user(user_id: str) -> dict[str, str]:
    return {"user_id": user_id, "stub": "true"}
