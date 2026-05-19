"""Handler: fetches full documents from Qdrant and reranks them."""

import logging
from typing import Any

from shared.schemas import RankJob, SearchResponse

from .qdrant_store import get_documents
from .ranker import rank

log = logging.getLogger("ranking_and_rendering.handler")


def build_result_item(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we expose to the FE for each document.

    Anything that's not in the Qdrant payload comes back as ``None`` and the
    FE hides empty slots.
    """
    payload = doc.get("payload", {})
    return {
        "id": doc["id"],
        "price": payload.get("price"),
        "property_type": payload.get("property_type"),
        "property_subtype": payload.get("property_subtype"),
        "street": payload.get("street"),
        "neighborhood": payload.get("neighborhood"),
        "district": payload.get("district"),
        "rooms": payload.get("rooms"),
        "bathrooms": payload.get("bathrooms"),
        "surface": payload.get("surface"),
        "floor": payload.get("floor"),
        "is_exterior": payload.get("is_exterior"),
        "has_elevator": payload.get("has_elevator"),
        "images": payload.get("images"),
        "url": payload.get("url"),
        "description": payload.get("description"),
        "score": doc.get("computed_score"),
    }


def handle(job: RankJob) -> SearchResponse:
    """Orchestrates the retrieval and reranking of documents."""

    log.info("handle: request_id=%s doc_ids=%s filters=%s", job.request_id, job.doc_ids, job.fields)

    # Retrieve full documents from Qdrant
    docs = get_documents(job.doc_ids)
    docs = [doc | {"score": score} for doc, score in zip(docs, job.doc_scores, strict=True)]

    log.debug("handle: received %d docs from Qdrant", len(docs))

    # Rerank based on filters
    ranked = rank(docs, job.fields)
    # Build the list of results for the frontend
    results: list[dict[str, Any]] = [build_result_item(doc) for doc in ranked]

    log.info("handle: ranked %d documents", len(results))
    return SearchResponse(request_id=job.request_id, results=results)
