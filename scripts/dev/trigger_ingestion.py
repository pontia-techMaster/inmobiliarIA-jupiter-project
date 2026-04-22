"""Publish an ``IngestJob`` to ``ingest-jobs`` to trigger data_ingestion manually.

A scheduled task (EventBridge in cloud, cron locally) will do this job later;
for now, run this script to simulate it.
"""

import sys

from shared.schemas import IngestJob
from shared.settings import settings
from shared.sqs import publish


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "/data/html"
    publish(settings.queue_ingest_jobs, IngestJob(source=source))
    print(f"triggered ingestion for {source}")


if __name__ == "__main__":
    main()
