"""Gemini embedding wrapper with stub fallback.

If ``GEMINI_API_KEY`` is set, calls the real Google Gemini embedding API via
``langchain-google-genai``. If not, returns a deterministic stub vector
(hash-derived) so the rest of the pipeline can run end-to-end without the
external dependency. Stub vectors are NOT meaningfully searchable — they
exist purely to verify plumbing.
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
from functools import lru_cache

from embeddings.config import DIMENSIONS, DOCUMENT_TASK_TYPE, MODEL, QUERY_TASK_TYPE

log = logging.getLogger("embeddings.gemini")


def _gemini_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _stub_vector(text: str) -> list[float]:
    """Deterministic pseudo-vector derived from the text hash. Same text → same vector."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    floats: list[float] = []
    while len(floats) < DIMENSIONS:
        for i in range(0, len(digest), 4):
            f = struct.unpack("f", digest[i : i + 4])[0]
            if f == f:  # filter out NaN
                floats.append(float(f))
            if len(floats) >= DIMENSIONS:
                break
        digest = hashlib.sha256(digest).digest()
    # normalize to unit length so cosine distance behaves
    norm = sum(x * x for x in floats) ** 0.5 or 1.0
    return [x / norm for x in floats]


@lru_cache(maxsize=2)
def _client(task_type: str):
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=f"models/{MODEL}",
        task_type=task_type,
        output_dimensionality=DIMENSIONS,
        google_api_key=_gemini_key(),
    )


def embed_query(text: str) -> list[float]:
    if not _gemini_key():
        log.warning("GEMINI_API_KEY not set — using STUB embedding for query")
        return _stub_vector(text)
    log.info("embedding query via Gemini (%s, %d dim)", MODEL, DIMENSIONS)
    return _client(QUERY_TASK_TYPE).embed_query(text)


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not _gemini_key():
        log.warning("GEMINI_API_KEY not set — using STUB embeddings for %d docs", len(texts))
        return [_stub_vector(t) for t in texts]
    log.info("embedding %d documents via Gemini (%s, %d dim)", len(texts), MODEL, DIMENSIONS)
    return _client(DOCUMENT_TASK_TYPE).embed_documents(texts)
