"""Bootstrap local Qdrant with the parsed properties from ``Old/data``.

One-shot dev script. Reads ``parsed-properties.json`` and
``normalized-descriptions.json`` from ``Old/data``, embeds each property's
summary via the shared ``embeddings`` package, creates a ``properties``
collection in local Qdrant matching the configured dimension and cosine
distance, and upserts all records with a payload of filterable fields.

The vector dimension is taken from ``embeddings.config.DIMENSIONS`` so
flipping that constant propagates here automatically. Re-running is safe —
the collection is recreated each time.

Note: this script previously reused the pre-computed 3072-dim vectors in
``Old/data/embeddings.json``, but those are no longer compatible with the
current ``DIMENSIONS`` (768). We now exercise the same embedding code that
``data_ingestion`` will use, which is also why this script is a small
preview of that worker.

Usage:
    make bootstrap
"""

from __future__ import annotations

import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from shared.embeddings import EMBEDDINGS_DIMENSIONALITY, embed_texts
from shared.settings import settings

ROOT = Path(__file__).resolve().parents[2]
PARSED = ROOT / "Old" / "data" / "parsed-properties.json"
DESCRIPTIONS = ROOT / "Old" / "data" / "normalized-descriptions.json"


def main() -> None:
    parsed = json.loads(PARSED.read_text())
    descriptions = json.loads(DESCRIPTIONS.read_text())

    properties = parsed["properties"]
    print(f"loaded {len(properties)} properties, {len(descriptions)} descriptions")

    # Embed the normalized summary of each property (falling back to its raw
    # description if no summary is available). Same code path data_ingestion
    # will use; respects GEMINI_API_KEY / stub fallback.
    texts = [descriptions.get(str(p["idealista_id"])) or p.get("description") or "" for p in properties]
    vectors = embed_texts(texts)
    print(f"embedded {len(vectors)} documents (dim={len(vectors[0])})")

    assert len(vectors[0]) == EMBEDDINGS_DIMENSIONALITY, f"expected {EMBEDDINGS_DIMENSIONALITY}-dim vectors, got {len(vectors[0])}"

    client = QdrantClient(url=settings.qdrant_url)
    collection = settings.qdrant_collection

    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=EMBEDDINGS_DIMENSIONALITY, distance=Distance.COSINE),
    )
    print(f"collection {collection!r} created (size={EMBEDDINGS_DIMENSIONALITY}, distance=COSINE)")

    points = []
    for prop, vector in zip(properties, vectors, strict=True):
        idealista_id = str(prop["idealista_id"])
        payload = {
            "idealista_id": prop["idealista_id"],
            "district": prop.get("district"),
            "neighborhood": prop.get("neighborhood"),
            "property_type": prop.get("property_type"),
            "property_subtype": prop.get("property_subtype"),
            "price": prop.get("price"),
            "rooms": prop.get("rooms"),
            "bathrooms": prop.get("bathrooms"),
            "surface": prop.get("surface"),
            "street": prop.get("street"),
            "summary": descriptions.get(idealista_id),
        }
        points.append(PointStruct(id=prop["idealista_id"], vector=vector, payload=payload))

    client.upsert(collection_name=collection, points=points)
    print(f"upserted {len(points)} points")


if __name__ == "__main__":
    main()
