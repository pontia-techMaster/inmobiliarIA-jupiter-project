"""Handler: fetches full documents from Qdrant and reranks them."""

import logging
from typing import Any

from shared.schemas import RankJob, SearchResponse

from .qdrant_client import get_documents
from .ranker import rank

log = logging.getLogger("ranking_and_rendering.handler")


def build_result_item(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we want to expose to the FE from each document.
    Adjust according to the fields saved in Qdrant.
    """
    payload = doc.get("payload", {})
    return {
        "id": doc["id"],
        "title": payload.get("title", f"Propiedad {doc['id']}"),
        "price": payload.get("price"),
        "city": payload.get("city"),
        "rooms": payload.get("rooms"),
        "score": doc.get("score"),
    }


def handle(job: RankJob) -> SearchResponse:
    """Orchestrates the retrieval and reranking of documents."""

    log.info("handle: request_id=%s doc_ids=%s filters=%s", job.request_id, job.doc_ids, job.filters)

    # Retrieve full documents from Qdrant
    docs = get_documents(job.doc_ids)

    log.debug("handle: received %d docs from Qdrant", len(docs))

    # Rerank based on filters
    ranked = rank(docs, job.filters)
    # Build the list of results for the frontend
    results: list[dict[str, Any]] = [build_result_item(doc) for doc in ranked]

    log.info("handle: ranked %d documents", len(results))
    return SearchResponse(request_id=job.request_id, results=results)
