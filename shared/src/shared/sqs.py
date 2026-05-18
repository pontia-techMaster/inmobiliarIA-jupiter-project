"""Thin boto3 SQS wrapper used by every service.

``publish`` serializes a Pydantic model and sends it to the named queue.
``consume`` long-polls the queue forever, yielding parsed messages. Each
message is deleted from the queue after the caller's iteration step returns,
so a handler that raises will leave the message visible again for redelivery.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Iterator
from typing import TypeVar

import boto3
from pydantic import BaseModel

from shared.settings import settings

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


def _client():
    # Local dev (ElasticMQ): pass endpoint + dummy creds explicitly.
    # Cloud (Lambda): SQS_ENDPOINT_URL="" — let boto3 use the regional
    # endpoint and pick up creds from the Lambda execution role.
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.sqs_endpoint_url:
        kwargs["endpoint_url"] = settings.sqs_endpoint_url
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("sqs", **kwargs)


@functools.lru_cache(maxsize=8)
def _queue_url(name: str) -> str:
    """Resolve queue URL via the SQS API. Cached for the life of the process.

    Works against both ElasticMQ and real SQS without hardcoding URL
    formats. Costs one ``GetQueueUrl`` call per queue per cold start.
    """
    return _client().get_queue_url(QueueName=name)["QueueUrl"]


def publish(queue_name: str, message: BaseModel) -> None:
    _client().send_message(
        QueueUrl=_queue_url(queue_name),
        MessageBody=message.model_dump_json(),
    )
    log.info("→ publish %s %s", queue_name, message.model_dump_json())


def consume(queue_name: str, model_cls: type[M]) -> Iterator[M]:  # noqa: UP047
    url = _queue_url(queue_name)
    client = _client()
    log.info("⟲ consume %s starting (long-poll)", queue_name)
    while True:
        resp = client.receive_message(
            QueueUrl=url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
        )
        for raw in resp.get("Messages", []):
            msg = model_cls.model_validate_json(raw["Body"])
            log.info("← consume %s %s", queue_name, msg.model_dump_json())
            yield msg
            client.delete_message(QueueUrl=url, ReceiptHandle=raw["ReceiptHandle"])
