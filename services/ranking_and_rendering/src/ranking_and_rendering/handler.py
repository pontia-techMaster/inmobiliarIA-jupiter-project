"""Stub handler: returns hardcoded results for the doc ids on the input job.

Real implementation will fetch full documents from Qdrant via
``qdrant_client`` and rerank them using ``ranker`` + the filters on the
input job.
"""

import logging

from shared.schemas import RankJob, SearchResponse

log = logging.getLogger("ranking_and_rendering.handler")


def handle(job: RankJob) -> SearchResponse:
    results = [{"id": doc_id, "title": f"Piso {doc_id}", "score": 0.9 - i * 0.1} for i, doc_id in enumerate(job.doc_ids)]
    log.info(
        "stub handler: request_id=%s doc_ids=%s filters=%s → %d results",
        job.request_id,
        job.doc_ids,
        job.filters,
        len(results),
    )
    return SearchResponse(request_id=job.request_id, results=results)
