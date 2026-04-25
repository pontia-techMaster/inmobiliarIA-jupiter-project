"""Stub handler: returns hardcoded doc ids and echoes filters, ignoring the input.

Real implementation will build filters from ``PromptFields.fields``, embed the
prompt via ``embeddings``, and run a filtered similarity search against Qdrant
via ``qdrant_client``.
"""

import logging

from shared.schemas import PromptFields, RankJob

log = logging.getLogger("vector_query.handler")


def handle(job: PromptFields) -> RankJob:
    log.info("stub handler: request_id=%s fields=%s → doc_ids=['doc-1','doc-2']", job.request_id, job.fields)
    return RankJob(
        request_id=job.request_id,
        doc_ids=["doc-1", "doc-2"],
        filters=job.fields,
    )
