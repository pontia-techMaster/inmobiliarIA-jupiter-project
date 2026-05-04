"""
Ranking logic with extended filters.

This function applies score adjustments to each document based on the filters
provided by the user. The goal is to prioritize properties that best match
the search criteria and penalize those that deviate.
"""

import logging
from typing import Any

from .ranking_rules import RANKING_RULES

log = logging.getLogger("ranking_and_rendering.ranker")


def rank(
    documents: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Sorts a list of documents using the user's filters.

    Each document must have:
      - score: initial score, e.g., the embedding similarity.
      - payload: property information.

    Supported filters:
      - city (str): exact city.
      - max_price (float/int): maximum price.
      - min_price (float/int): minimum price.
      - min_rooms (int): minimum number of rooms.
      - property_type (str): apartment, house, etc.
      - property_subtype (str): flat, duplex, penthouse, chalet, etc.
      - neighborhood (str): exact neighborhood.
      - district (str): exact district.
      - min_surface (int): minimum surface area in m².
      - max_surface (int): maximum surface area in m².
      - min_bathrooms (int): minimum number of bathrooms.
      - floor (str | list): desired floor. Example: "2" or ["1", "2", "3"].
      - is_exterior (bool): True for exterior, False for interior.
      - has_elevator (bool): True if elevator is required, False otherwise.

    Returns:
      - List of documents sorted from highest to lowest score.
    """
    log.debug("Ranking %d documents with filters %s", len(documents), filters)

    ranked: list[dict[str, Any]] = []

    for doc in documents:
        score = float(doc.get("score", 1.0))
        original = score

        payload = doc.get("payload", {})
        log.debug("Doc %s initial score: %s", doc.get("id"), original)
        for rule in RANKING_RULES:
            score = rule.apply(
                score=score,
                payload=payload,
                filters=filters,
            )

        ranked_doc = {
            **doc,
            "score": score,
        }
        log.debug("Doc %s final score: %s", doc.get("id"), score)
        ranked.append(ranked_doc)

    ranked.sort(
        key=lambda document: document["score"],
        reverse=True,
    )
    log.info("Finished ranking %d documents", len(ranked))
    return ranked
