"""AWS Lambda entrypoint for ``ranking_and_rendering``.

Invoked by the SQS event source mapping with a batch of messages from
``rank-jobs``. Same ``handle()`` function as ``worker.py``; only the
I/O wrapper changes.
"""

from __future__ import annotations

import logging
import os


def _ssm_to_env(env_var: str, param_var: str) -> None:
    if os.environ.get(env_var):
        return
    param = os.environ.get(param_var)
    if not param:
        return
    import boto3

    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=param, WithDecryption=True)
    os.environ[env_var] = resp["Parameter"]["Value"]


_ssm_to_env("QDRANT_API_KEY", "QDRANT_API_KEY_PARAM")

from shared.schemas import RankJob  # noqa: E402
from shared.settings import settings  # noqa: E402
from shared.sqs import publish  # noqa: E402

from ranking_and_rendering.handler import handle  # noqa: E402

logging.basicConfig(level=logging.INFO, force=True)
log = logging.getLogger("ranking_and_rendering.lambda")


def handler(event: dict, context: object) -> dict:
    records = event.get("Records", [])
    log.info("invoked records=%d", len(records))

    for record in records:
        job = RankJob.model_validate_json(record["body"])
        log.info("processing request_id=%s", job.request_id)
        out = handle(job)
        if out is not None:
            publish(settings.queue_search_responses, out)

    return {"batchItemFailures": []}
