"""AWS Lambda entrypoint for ``data_ingestion``.

Two trigger paths in cloud:
  - Scheduled EventBridge rule publishes an ``IngestJob`` to ``ingest-jobs``,
    which event-source-maps into this Lambda.
  - Manual: someone publishes to ``ingest-jobs`` directly.

In cloud the ``source`` field in ``IngestJob`` points at an S3 prefix. We
download the HTML files to /tmp before handing them to ``handle()``,
which expects a local Path (kept as-is for parity with local docker
runs).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path


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


_ssm_to_env("GEMINI_API_KEY", "GEMINI_API_KEY_PARAM")
_ssm_to_env("QDRANT_API_KEY", "QDRANT_API_KEY_PARAM")

from shared.schemas import IngestJob  # noqa: E402

from data_ingestion.handler import handle  # noqa: E402

logging.basicConfig(level=logging.INFO, force=True)
log = logging.getLogger("data_ingestion.lambda")


def _sync_s3_to_local(bucket: str, prefix: str, dest: Path) -> Path:
    """Copy every object under s3://bucket/prefix to dest/. Returns dest."""
    import boto3

    s3 = boto3.client("s3")
    dest.mkdir(parents=True, exist_ok=True)
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key: str = obj["Key"]
            if key.endswith("/"):
                continue
            rel = key.removeprefix(prefix).lstrip("/")
            local_path = dest / rel
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(local_path))
            count += 1
    log.info("synced %d objects from s3://%s/%s to %s", count, bucket, prefix, dest)
    return dest


def handler(event: dict, context: object) -> dict:
    records = event.get("Records", [])
    log.info("invoked records=%d", len(records))

    for record in records:
        job = IngestJob.model_validate_json(record["body"])
        log.info("processing source=%s", job.source)

        # If source is an s3:// URL, sync to /tmp first.
        if job.source.startswith("s3://"):
            without_scheme = job.source.removeprefix("s3://")
            bucket, _, prefix = without_scheme.partition("/")
            local = _sync_s3_to_local(bucket, prefix, Path("/tmp/ingest"))
            job = IngestJob(source=str(local))

        handle(job)

    return {"batchItemFailures": []}
