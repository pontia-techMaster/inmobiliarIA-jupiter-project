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

from qdrant_client.models import Condition, FieldCondition, Filter, MatchAny, MatchValue
from shared.schemas import PromptField

log = logging.getLogger("vector_query.filters")

_KEY_MATCH_CONDITIONS_MAPPING = {
    # lte = "lower or equal", gte = "greater or equal"
    "property_type": "equal",
    "is_exterior": "equal",
    "has_elevator": "equal",
    "location": "equal",
    "price": "lte",
    "rooms": "gte",
    "bathrooms": "gte",
    "surface": "gte",
}


def build(fields: list[PromptField]) -> Filter | None:
    """Return a Qdrant ``Filter``, or ``None`` if no recognised filter fields are present."""

    must: list[Condition] = []

    for field in fields:
        field_value: list = field.value or []
        field_name: str = field.name or ""

        condition = _KEY_MATCH_CONDITIONS_MAPPING.get(field_name)
        if not condition:
            log.info(f"ignoring unknown filter key: {field_name}")

        if condition == "equal":
            if field_name in {"property_type", "location"}:
                if len(set(field_value)) == 1:
                    must.append(FieldCondition(key=field_name, match=MatchValue(value=field_value[0])))
                else:
                    must.append(FieldCondition(key=field_name, match=MatchAny(any=field_value)))
            else:  # is_exterior or has_elevator
                must.append(FieldCondition(key=field_name, match=MatchValue(value=all(field_value))))
        elif condition == "lte":
            must.append(FieldCondition(key=field_name, match=MatchValue(value=max(field_value))))
        elif condition == "gte":
            must.append(FieldCondition(key=field_name, match=MatchValue(value=min(field_value))))
        else:
            log.info(f"ignoring unknown condition: {condition}")

    if not must:
        return None

    return Filter(must=must)
