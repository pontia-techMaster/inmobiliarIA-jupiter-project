"""Translate ``PromptFields.fields`` into a Qdrant ``Filter`` expression.

Recognised keys (anything else is silently ignored — see ``_KNOWN``):

    Exact-match (string):
        district, neighborhood, property_type, property_subtype

    Numeric ranges:
        min_price / max_price       → payload field ``price``
        min_rooms / max_rooms       → payload field ``rooms``
        min_surface / max_surface   → payload field ``surface``

The contract here is shared with ``data_ingestion``: the payload it writes to
Qdrant must use these same field names.
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

log = logging.getLogger("vector_query.filters")

_EXACT = ("district", "neighborhood", "property_type", "property_subtype")
_RANGES = {
    "price": ("min_price", "max_price"),
    "rooms": ("min_rooms", "max_rooms"),
    "surface": ("min_surface", "max_surface"),
}
_KNOWN = set(_EXACT) | {k for pair in _RANGES.values() for k in pair}


def build(fields: dict[str, Any]) -> Filter | None:
    """Return a Qdrant ``Filter``, or ``None`` if no recognised filter fields are present."""

    must: list[FieldCondition] = []

    for key in _EXACT:
        value = fields.get(key)
        if value is not None:
            must.append(FieldCondition(key=key, match=MatchValue(value=value)))

    for payload_key, (min_key, max_key) in _RANGES.items():
        lo = fields.get(min_key)
        hi = fields.get(max_key)
        if lo is not None or hi is not None:
            must.append(FieldCondition(key=payload_key, range=Range(gte=lo, lte=hi)))

    unknown = [k for k in fields if k not in _KNOWN]
    if unknown:
        log.info("ignoring unknown filter keys: %s", unknown)

    if not must:
        return None
    return Filter(must=must)
