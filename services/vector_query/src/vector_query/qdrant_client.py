"""Qdrant similarity-search wrapper.

Exposes a single ``search`` function that runs a filtered nearest-neighbours
query against the configured collection and returns a list of ``(id, score)``
hits sorted by descending similarity.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from shared.settings import settings

log = logging.getLogger("vector_query.qdrant_client")


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    log.info("connecting to Qdrant at %s", settings.qdrant_url)
    return QdrantClient(url=settings.qdrant_url)


def search(vector: list[float], qfilter: Filter | None, k: int) -> list[tuple[str, float]]:
    hits = (
        _client()
        .query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            query_filter=qfilter,
            limit=k,
            with_payload=False,
        )
        .points
    )
    return [(str(hit.id), float(hit.score)) for hit in hits]
