"""One-off: create payload indexes on the Qdrant Cloud `properties` collection.

Qdrant doesn't index payload fields by default; vector_query.filters needs
indexes on every key it filters on, otherwise the search API returns:
    Bad request: Index required but not found for "<field>" of one of the
    following types: [keyword]

This is idempotent — re-running is safe; an "already exists" response is
just logged and skipped.

Usage:
    uv run python scripts/cloud/create_qdrant_indexes.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType


def _load_local_client() -> QdrantClient:
    """Load secrets/qdrantcloud.py by path.

    ``import secrets.qdrantcloud`` collides with the stdlib ``secrets``
    module, so we sidestep the import system entirely. The file is
    gitignored; for prod we'd read URL + key from SSM instead.
    """
    secrets_file = Path(__file__).resolve().parents[2] / "secrets" / "qdrantcloud.py"
    spec = importlib.util.spec_from_file_location("_qdrantcloud", secrets_file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.qdrant_client


_client = _load_local_client()

# Field schemas — kept in lockstep with what vector_query.filters expects.
INDEXES: list[tuple[str, PayloadSchemaType]] = [
    # exact-match (keyword)
    ("property_type", PayloadSchemaType.KEYWORD),
    ("is_exterior", PayloadSchemaType.BOOL),
    ("has_elevator", PayloadSchemaType.BOOL),
    ("location", PayloadSchemaType.KEYWORD),
    ("district", PayloadSchemaType.KEYWORD),
    ("neighborhood", PayloadSchemaType.KEYWORD),
    # numeric range
    ("price", PayloadSchemaType.INTEGER),
    ("rooms", PayloadSchemaType.INTEGER),
    ("surface", PayloadSchemaType.INTEGER),
    ("bathrooms", PayloadSchemaType.INTEGER),
]

COLLECTION = "properties"


def main() -> None:
    client: QdrantClient = _client  # imported singleton from secrets/qdrantcloud.py
    print(f"Connecting to {COLLECTION} on Qdrant Cloud…")

    for field, schema in INDEXES:
        try:
            client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=schema,
            )
            print(f"  ✓ {field:<20} ({schema.value})")
        except Exception as e:
            # "already exists" / 409 / etc — fine, no-op.
            msg = str(e).splitlines()[0][:120]
            print(f"  ⊘ {field:<20} ({schema.value})  — {msg}")


if __name__ == "__main__":
    main()
