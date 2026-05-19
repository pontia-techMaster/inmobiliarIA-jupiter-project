"""AWS Lambda entrypoint for ``ranking_and_rendering``.

Invoked by the SQS event source mapping with a batch of messages from
``rank-jobs``. Same ``handle()`` function as ``worker.py``; only the
I/O wrapper changes.
"""

from __future__ import annotations

import logging
import os
import time


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

# DDB write is opt-in via env vars. Local-dev has neither, so it skips.
_SEARCH_RESULTS_TABLE = os.environ.get("SEARCH_RESULTS_TABLE", "")
_SEARCH_RESULTS_TTL = int(os.environ.get("SEARCH_RESULTS_TTL_SECONDS", "300"))


def _store_result(request_id: str, result_json: str) -> None:
    """Write the SearchResponse to DDB so the results-api Lambda can serve it
    over HTTP. Idempotent — repeated writes for the same request_id just
    overwrite the row."""
    if not _SEARCH_RESULTS_TABLE:
        return
    import boto3

    ddb = boto3.client("dynamodb")
    ddb.put_item(
        TableName=_SEARCH_RESULTS_TABLE,
        Item={
            "request_id": {"S": request_id},
            "result": {"S": result_json},
            "expires_at": {"N": str(int(time.time()) + _SEARCH_RESULTS_TTL)},
        },
    )
    log.info("stored result for request_id=%s in %s", request_id, _SEARCH_RESULTS_TABLE)


def _store_user_search(job: RankJob, out_payload: dict) -> None:
    """Write a row to the durable user-searches table.

    Only fires when a user_id is present (the FE supplies one via
    localStorage). Swallows exceptions so a history-write failure doesn't
    fail the search itself.
    """
    if not job.user_id:
        return
    try:
        from shared.ddb import put_user_search  # local import — keeps cold start lean

        put_user_search(
            user_id=job.user_id,
            request_id=job.request_id,
            prompt=job.prompt,
            result=out_payload,
        )
        log.info("wrote user-searches row for user=%s request=%s", job.user_id, job.request_id)
    except Exception:
        log.exception("failed to write user-searches row for %s", job.request_id)


def handler(event: dict, context: object) -> dict:
    records = event.get("Records", [])
    log.info("invoked records=%d", len(records))

    for record in records:
        job = RankJob.model_validate_json(record["body"])
        log.info("processing request_id=%s", job.request_id)
        out = handle(job)
        if out is not None:
            publish(settings.queue_search_responses, out)
            _store_result(out.request_id, out.model_dump_json())
            _store_user_search(job, out.model_dump())

    return {"batchItemFailures": []}
