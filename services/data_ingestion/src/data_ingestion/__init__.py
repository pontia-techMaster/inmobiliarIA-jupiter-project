"""data_ingestion: SQS worker that ingests property HTML into Qdrant.

Triggered by a scheduled task that publishes ``IngestJob`` onto ``ingest-jobs``
(EventBridge in cloud, cron or manual trigger in local dev). The worker parses
HTML from the given source, generates embeddings, and writes documents to
Qdrant.

Real parsing / embedding / Qdrant write live in ``html_parser``,
``embeddings`` and ``qdrant_client`` (empty for now); ``handler`` is the
stubbed transform and just logs what it would do.
"""
