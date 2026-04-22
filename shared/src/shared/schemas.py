"""Pydantic message schemas exchanged between services via SQS.

Every message carries a ``request_id`` so workers can correlate the stages of a
single search through the chain, and so the frontend can match a response to
the request that produced it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Payload posted by the frontend to /search and forwarded onto ``search-requests``."""

    request_id: str
    prompt: str
    user_id: str | None = None


class PromptFields(BaseModel):
    """Structured fields extracted from the natural-language prompt by ``process_user_prompt``."""

    request_id: str
    fields: dict[str, Any] = Field(default_factory=dict)


class QueryJob(BaseModel):
    """Message on ``query-jobs``: input for ``vector_query``."""

    request_id: str
    fields: dict[str, Any]


class RankJob(BaseModel):
    """Message on ``rank-jobs``: candidate doc ids + filters, input for ``ranking_and_rendering``."""

    request_id: str
    doc_ids: list[str]
    filters: dict[str, Any]


class SearchResponse(BaseModel):
    """Final payload on ``search-responses``, consumed by the frontend."""

    request_id: str
    results: list[dict[str, Any]]


class IngestJob(BaseModel):
    """Message on ``ingest-jobs``: tells ``data_ingestion`` to process an HTML source."""

    source: str
