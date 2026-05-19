"""process_user_prompt: SQS worker that extracts structured fields from a natural-language prompt.

Consumes ``SearchRequest`` messages from ``search-requests`` and publishes
``PromptFields`` messages to ``query-jobs``, preserving ``request_id`` so
downstream workers can correlate the whole search chain.

The real LLM call lives in ``llm_client`` (empty for now); ``handler`` is the
stubbed input→output transform and returns hardcoded fields.
"""
