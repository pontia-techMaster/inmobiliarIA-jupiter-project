"""Handler: fetches full documents from Qdrant and reranks them."""

import logging
from typing import Any

from shared.schemas import RankJob, SearchResponse

from .qdrant_store import get_documents
from .ranker import rank

log = logging.getLogger("ranking_and_rendering.handler")


def build_result_item(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we want to expose to the FE from each document.
    Adjust according to the fields saved in Qdrant.
    """
    payload = doc.get("payload", {})
    return {
        "id": doc["id"],
        "price": payload.get("price"),
        "street": payload.get("street"),
        "neighborhood": payload.get("neighborhood"),
        "district": payload.get("district"),
        "rooms": payload.get("rooms"),
        "surface": payload.get("surface"),
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
