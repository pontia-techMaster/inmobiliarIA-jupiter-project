"""ranking_and_rendering: SQS worker that fetches full docs and ranks them.

Consumes ``RankJob`` (doc ids + filters) from ``rank-jobs`` and publishes a
``SearchResponse`` (ranked results) to ``search-responses``, preserving
``request_id`` so the frontend can match the response to its request.

Real doc fetch and ranking live in ``qdrant_client`` and ``ranker`` (empty
for now); ``handler`` is the stubbed transform and returns hardcoded results.
"""
