"""SQS loop: consume ``search-requests``, hand each message to the handler, publish to ``query-jobs``."""

from __future__ import annotations

import logging

from shared.schemas import SearchRequest
from shared.settings import settings
from shared.sqs import consume, publish

from process_user_prompt.handler import handle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)
log = logging.getLogger("process_user_prompt.worker")


def main() -> None:
    log.info("process_user_prompt worker starting")
    for req in consume(settings.queue_search_requests, SearchRequest):
        out = handle(req)
        publish(settings.queue_query_jobs, out)


if __name__ == "__main__":
    main()
