"""AWS Lambda entrypoint for ``process_user_prompt``.

Invoked by the SQS event source mapping with a batch of messages from
``search-requests``. Same ``handle()`` function as ``worker.py``; only
the I/O wrapper changes.
"""

from __future__ import annotations

import logging
import os

# Resolve GEMINI_API_KEY from SSM Parameter Store at cold start, before
# importing the handler (whose `langchain_google_genai` import path
# constructs a client that hard-validates the key). One ssm:GetParameter
# call per cold start; cached for the life of the container.
if not os.environ.get("GEMINI_API_KEY") and (_param := os.environ.get("GEMINI_API_KEY_PARAM")):
    import boto3

    _ssm = boto3.client("ssm")
    _resp = _ssm.get_parameter(Name=_param, WithDecryption=True)
    os.environ["GEMINI_API_KEY"] = _resp["Parameter"]["Value"]

from shared.schemas import SearchRequest  # noqa: E402
from shared.settings import settings  # noqa: E402
from shared.sqs import publish  # noqa: E402

from process_user_prompt.handler import handle  # noqa: E402

logging.basicConfig(level=logging.INFO, force=True)
log = logging.getLogger("process_user_prompt.lambda")


def handler(event: dict, context: object) -> dict:
    region = os.environ.get("AWS_REGION", "?")
    records = event.get("Records", [])
    log.info("invoked region=%s records=%d", region, len(records))

    for record in records:
        req = SearchRequest.model_validate_json(record["body"])
        log.info("processing request_id=%s", req.request_id)
        out = handle(req)
        if out is not None:
            publish(settings.queue_query_jobs, out)

    return {"batchItemFailures": []}
