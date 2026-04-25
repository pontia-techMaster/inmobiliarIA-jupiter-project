"""Thin boto3 SQS wrapper used by every service.

``publish`` serializes a Pydantic model and sends it to the named queue.
``consume`` long-polls the queue forever, yielding parsed messages. Each
message is deleted from the queue after the caller's iteration step returns,
so a handler that raises will leave the message visible again for redelivery.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TypeVar

import boto3
from pydantic import BaseModel

from shared.settings import settings

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


def _client():
    return boto3.client(
        "sqs",
        endpoint_url=settings.sqs_endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _queue_url(name: str) -> str:
    return f"{settings.sqs_endpoint_url}/000000000000/{name}"


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
