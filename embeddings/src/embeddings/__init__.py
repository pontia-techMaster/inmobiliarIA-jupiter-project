"""Shared embedding wrapper.

Used by ``vector_query`` (queries) and ``data_ingestion`` (documents) to
guarantee both sides produce vectors in the same space — the model name and
dimensionality live here in ``config`` and are imported by both services.

Public API:
    embed_query(text)        — for search prompts
    embed_documents(texts)   — for property descriptions

If ``GEMINI_API_KEY`` is unset, a deterministic stub is used instead so the
pipeline runs end-to-end without the external API. Set the key to switch to
real Gemini embeddings.
"""

from embeddings.gemini import embed_documents, embed_query

__all__ = ["embed_query", "embed_documents"]
