"""SQS loop: consume ``rank-jobs``, hand each message to the handler, publish to ``search-responses``."""

from __future__ import annotations

import logging

from shared.ddb import ensure_user_searches_table, put_user_search
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
    # Don't let a slow/unreachable DDB at startup kill the worker — the search
    # path doesn't need the history table; only the per-message write below does.
    try:
        ensure_user_searches_table()
    except Exception:
        log.exception("ensure_user_searches_table failed; continuing without it")
    for job in consume(settings.queue_rank_jobs, RankJob):
        out = handle(job)
        publish(settings.queue_search_responses, out)
        if job.user_id:
            try:
                put_user_search(
                    user_id=job.user_id,
                    request_id=out.request_id,
                    prompt=job.prompt,
                    result=out.model_dump(),
                )
            except Exception:
                # Don't fail the search if history write fails — the FE still
                # got its response on the queue.
                log.exception("failed to write user-searches row for %s", out.request_id)


if __name__ == "__main__":
    main()
