"""Orchestrates a single ``ProcessUserPromptResponse → RankJob`` transform.

Steps:

1. Embed the original natural-language prompt (``embed_query``).
2. Build a Qdrant filter from the structured ``fields`` (``filters.build``).
3. Run a filtered similarity search to get the top-K candidate doc ids.
4. Pack them into a ``RankJob`` for ``ranking_and_rendering`` to rerank.
"""

from __future__ import annotations

import logging

from shared.embeddings import embed_query
from shared.schemas import ProcessUserPromptResponse, RankJob
from shared.settings import settings

from vector_query.filters import build as build_filter
from vector_query.qdrant_store import search

log = logging.getLogger("vector_query.handler")


def handle(job: ProcessUserPromptResponse) -> RankJob:
    vector = embed_query(job.prompt)
    qfilter = build_filter(job.fields)
    hits = search(vector, qfilter, k=settings.qdrant_top_k)

    log.info(
        "request_id=%s prompt=%r filters=%s → %d hits (top score=%.4f)",
        job.request_id,
        job.prompt,
        qfilter.model_dump_json(),
        len(hits),
        hits[0][1] if hits else 0.0,
    )

    return RankJob(
        request_id=job.request_id,
        doc_ids=[doc_id for doc_id, _ in hits],
        doc_scores=[score for _, score in hits],
        fields=job.fields,
    )
