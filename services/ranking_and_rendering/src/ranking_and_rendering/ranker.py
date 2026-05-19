"""
Ranking logic with extended filters.

This function applies score adjustments to each document based on the filters
provided by the user. The goal is to prioritize properties that best match
the search criteria and penalize those that deviate.
"""

import logging
from collections.abc import Callable
from typing import Any

from shared.schemas import PromptField

from ranking_and_rendering.ranking_rules import (
    _compute_bathrooms_score,
    _compute_has_elevator_score,
    _compute_is_exterior_score,
    _compute_location_score,
    _compute_price_score,
    _compute_rooms_score,
    _compute_surface_score,
)

log = logging.getLogger("ranking_and_rendering.ranker")

type ScoreFunction = Callable[[dict, PromptField], float]

_FIELD_SCORE_MAPPING: dict[str, tuple[ScoreFunction, float]] = {
    "price": (_compute_price_score, 0.3),
    "rooms": (_compute_rooms_score, 0.2),
    "location": (_compute_location_score, 0.2),
    "surface": (_compute_surface_score, 0.15),
    "bathrooms": (_compute_bathrooms_score, 0.08),
    "has_elevator": (_compute_has_elevator_score, 0.04),
    "is_exterior": (_compute_is_exterior_score, 0.03),
}
_SEMANTIC_WEIGHT = 0.10


def _compute_score(payload: dict, fields: list[PromptField], semantic_score: float) -> float:

    active_fields = [f for f in fields if f.name in _FIELD_SCORE_MAPPING]
    total_field_weight = sum(_FIELD_SCORE_MAPPING[f.name][1] for f in active_fields)

    weighted_field_score = 0.0
    for field in fields:
        field_name = field.name
        if field_name not in _FIELD_SCORE_MAPPING:
            continue

        score_function, weight = _FIELD_SCORE_MAPPING[field_name]
        score = score_function(payload, field)

        normalized_weight = (weight / total_field_weight) * (1.0 - _SEMANTIC_WEIGHT)
        weighted_field_score += score * normalized_weight

    final_score = weighted_field_score + _SEMANTIC_WEIGHT * semantic_score
    return round(final_score, 4)


def rank(
    documents: list[dict[str, Any]],
    fields: list[PromptField],
) -> list[dict[str, Any]]:
    """
    Sorts a list of documents using the user's filters.

    Each document must have:
      - score: initial score, e.g., the embedding similarity.
      - payload: property information.

    Returns:
      - List of documents sorted from highest to lowest score.
    """
    log.debug("Ranking %d documents with filters %s", len(documents), fields)

    ranked: list[dict[str, Any]] = []

    for doc in documents:
        semantic_score = float(doc.get("score", 0.6))

        payload = doc.get("payload", {})
        log.debug("Doc %s semantic score: %s", doc.get("id"), semantic_score)
        score = _compute_score(payload, fields, semantic_score)

        ranked_doc = {
            **doc,
            "computed_score": score,
        }
        log.debug("Doc %s final score: %s", doc.get("id"), score)
        ranked.append(ranked_doc)

    ranked.sort(
        key=lambda document: document["computed_score"],
        reverse=True,
    )
    log.info("Finished ranking %d documents", len(ranked))
    return ranked
