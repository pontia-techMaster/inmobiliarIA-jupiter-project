"""Qdrant read client for full-document fetch."""

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Record
from shared.settings import settings

log = logging.getLogger("ranking_and_rendering.qdrant_store")
# Client global
_client: QdrantClient | None = None


# singleton
def get_client() -> QdrantClient:
    """Iniciated the Qdrant client on first call."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        log.info("Initialized Qdrant client at %s", settings.qdrant_url)
    return _client


def get_documents(doc_ids: list[str]) -> list[dict[str, Any]]:
    """Recuperated documents from Qdrant by their IDs.
    Returns a list of dictionaries with id, payload and score (initialized to 1.0 if Qdrant does not return score).
    """
    if not doc_ids:
        return []

    log.debug("Fetching %d documents from Qdrant", len(doc_ids))
    client = get_client()
    # Recuperated points without vector and with payload. Qdrant returns a list of PointStruct.
    try:
        retrieved: list[Record] = client.retrieve(
            collection_name=settings.qdrant_collection_name,
            ids=doc_ids,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        log.error("Error retrieving documents from Qdrant: %s", exc, exc_info=True)
        raise

    docs: list[dict[str, Any]] = []
    for point in retrieved:
        payload = point.payload or {}
        docs.append(
            {
                "id": point.id,
                "payload": payload,
                "score": payload.get("score", 1.0),
                # If we haven't saved the similarity score in Qdrant, we start from 1.0 as a base
            }
        )
    log.debug("Retrieved %d documents", len(docs))
    return docs
