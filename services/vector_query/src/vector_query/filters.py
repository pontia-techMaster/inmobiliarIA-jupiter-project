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
from collections import defaultdict
from typing import Literal

from qdrant_client.models import Condition, FieldCondition, Filter, MatchAny, MatchValue, Range
from shared.constants import (
    BATHROOMS_RELAXATION_COEFFICIENT,
    PRICE_RELAXATION_COEFFICIENT,
    ROOMS_RELAXATION_COEFFICIENT,
    SURFACE_RELAXATION_COEFFICIENT,
)
from shared.location_utils import resolve_location
from shared.schemas import PromptField

log = logging.getLogger("services.vector_query.filters")


def _build_property_type_filter(values: list[str], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    return [FieldCondition(key="property_type", match=MatchAny(any=values))]


def _build_location_filter(values: list[str], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    raw_filter = defaultdict(list)
    if strength == "hard":
        for value in values:
            resolved = resolve_location(query=value)
            if resolved:
                raw_filter[resolved.type].append(resolved.value)
    else:
        for value in values:
            resolved = resolve_location(query=value)
            if resolved:
                raw_filter["district"].append(resolved.parent_district if resolved.type == "neighborhood" else resolved.value)

    # process each value
    filters: list[FieldCondition] = []
    if _values := raw_filter.get("district", []):
        filters.append(FieldCondition(key="district", match=MatchAny(any=_values)))
    if _values := raw_filter.get("neighborhood", []):
        filters.append(FieldCondition(key="neighborhood", match=MatchAny(any=_values)))
    return filters


def _build_rooms_filter(values: list[int], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    if strength == "hard":
        return [FieldCondition(key="rooms", range=Range(gte=min(values)))]
    else:
        relaxed_value = max(1, min(values) - ROOMS_RELAXATION_COEFFICIENT)
        return [FieldCondition(key="rooms", range=Range(gte=relaxed_value))]


def _build_bathrooms_filter(values: list[int], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    if strength == "hard":
        return [FieldCondition(key="bathrooms", range=Range(gte=min(values)))]
    else:
        relaxed_value = max(1, min(values) - BATHROOMS_RELAXATION_COEFFICIENT)
        return [FieldCondition(key="bathrooms", range=Range(gte=relaxed_value))]


def _build_surface_filter(values: list[int], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    if strength == "hard":
        return [FieldCondition(key="surface", range=Range(gte=min(values)))]
    else:
        value = min(values)
        relaxed_value = int(value * (1 - SURFACE_RELAXATION_COEFFICIENT))
        return [FieldCondition(key="surface", range=Range(gte=relaxed_value))]


def _build_price_filter(values: list[int], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    if strength == "hard":
        return [FieldCondition(key="price", range=Range(lte=max(values)))]
    else:
        value = max(values)
        relaxed_value = int(value * (1 + PRICE_RELAXATION_COEFFICIENT))
        return [FieldCondition(key="price", range=Range(lte=relaxed_value))]


def _build_has_elevator_filter(values: list[bool], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    return [FieldCondition(key="has_elevator", match=MatchValue(value=all(values)))]


def _build_is_exterior_filter(values: list[bool], strength: Literal["soft", "hard"]) -> list[FieldCondition]:
    return [FieldCondition(key="is_exterior", match=MatchValue(value=all(values)))]


_FILTER_FUNCTION_MAPPING = {
    "property_type": _build_property_type_filter,
    "location": _build_location_filter,
    "rooms": _build_rooms_filter,
    "bathrooms": _build_bathrooms_filter,
    "surface": _build_surface_filter,
    "price": _build_price_filter,
    "has_elevator": _build_has_elevator_filter,
    "is_exterior": _build_is_exterior_filter,
}


def build(fields: list[PromptField]) -> Filter | None:
    """Return a Qdrant ``Filter``, or ``None`` if no recognised filter fields are present."""

    must: list[Condition] = []

    for field in fields:
        field_name = field.name

        filter_function = _FILTER_FUNCTION_MAPPING.get(field_name)
        if filter_function is None:
            log.info(f"not filter function defined for this key: {field_name}")
            continue

        field_value = field.value
        field_strength = field.strength

        must.extend(filter_function(field_value, field_strength))  # type: ignore

    if not must:
        return None

    return Filter(must=must)
