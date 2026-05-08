"""SQS loop: consume ``query-jobs``, hand each message to the handler, publish to ``rank-jobs``."""

from __future__ import annotations

import logging

from shared.schemas import ProcessUserPromptResponse
from shared.settings import settings
from shared.sqs import consume, publish

from vector_query.handler import handle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)
log = logging.getLogger("vector_query.worker")


def main() -> None:
    log.info("vector_query worker starting")
    for job in consume(settings.queue_query_jobs, ProcessUserPromptResponse):
        out = handle(job)
        publish(settings.queue_rank_jobs, out)


if __name__ == "__main__":
    main()
