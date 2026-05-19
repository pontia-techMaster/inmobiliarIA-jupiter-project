"""vector_query: SQS worker that runs a filtered similarity search against Qdrant.

Consumes ``PromptFields`` from ``query-jobs`` and publishes ``RankJob`` (doc
ids + filters) to ``rank-jobs``, preserving ``request_id``.

The real embedding and Qdrant calls live in ``embeddings`` and
``qdrant_client`` (empty for now); ``handler`` is the stubbed transform and
returns hardcoded doc ids.
"""
