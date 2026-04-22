"""SQS loop: consume ``ingest-jobs`` and hand each message to the handler."""

from __future__ import annotations

import logging

from shared.schemas import IngestJob
from shared.settings import settings
from shared.sqs import consume

from data_ingestion.handler import handle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)
log = logging.getLogger("data_ingestion.worker")


def main() -> None:
    log.info("data_ingestion worker starting")
    for job in consume(settings.queue_ingest_jobs, IngestJob):
        handle(job)


if __name__ == "__main__":
    main()
