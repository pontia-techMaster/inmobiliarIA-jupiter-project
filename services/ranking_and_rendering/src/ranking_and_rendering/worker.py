"""SQS loop: consume ``rank-jobs``, hand each message to the handler, publish to ``search-responses``."""

from __future__ import annotations

import logging

from shared.schemas import RankJob
from shared.settings import settings
from shared.sqs import consume, publish

from ranking_and_rendering.handler import handle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)
log = logging.getLogger("ranking_and_rendering.worker")


def main() -> None:
    log.info("ranking_and_rendering worker starting")
    for job in consume(settings.queue_rank_jobs, RankJob):
        out = handle(job)
        publish(settings.queue_search_responses, out)


if __name__ == "__main__":
    main()
