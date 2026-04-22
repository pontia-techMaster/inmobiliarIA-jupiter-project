"""Stub handler: logs the source it would ingest, does nothing else.

Real implementation will read HTML from ``job.source`` via ``html_parser``,
produce embeddings via ``embeddings``, and write documents into Qdrant via
``qdrant_client``.
"""

import logging

from shared.schemas import IngestJob

log = logging.getLogger("data_ingestion.handler")


def handle(job: IngestJob) -> None:
    log.info("stub handler: would ingest source=%r", job.source)
