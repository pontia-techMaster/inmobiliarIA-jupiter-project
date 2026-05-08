"""
Ranking logic with extended filters.

This function applies score adjustments to each document based on the filters
provided by the user. The goal is to prioritize properties that best match
the search criteria and penalize those that deviate.
"""

import logging
from typing import Any

from shared.schemas import PromptField

from .ranking_rules import RANKING_RULES

log = logging.getLogger("ranking_and_rendering.ranker")


def rank(
    documents: list[dict[str, Any]],
    fields: PromptField,
) -> list[dict[str, Any]]:
    """
    Sorts a list of documents using the user's filters.

    Each document must have:
      - score: initial score, e.g., the embedding similarity.
      - payload: property information.

    Supported filters:
      - price (float/int): price.
      - rooms (int): minimum number of rooms.
      - property_type (str): apartment or house
      - location (str): exact neighborhood. **NOT IMPLEMENTED**
      - is_exterior (bool): True for exterior, False for interior.
      - has_elevator (bool): True if elevator is required, False otherwise.

    Returns:
      - List of documents sorted from highest to lowest score.
    """
    log.debug("Ranking %d documents with filters %s", len(documents), filters)

    ranked: list[dict[str, Any]] = []

    _fields = {field.name: field for field in fields}

    for doc in documents:
        score = float(doc.get("score", 1.0))
        original = score

        payload = doc.get("payload", {})
        log.debug("Doc %s initial score: %s", doc.get("id"), original)
        for rule in RANKING_RULES:
            score = rule.apply(
                score=score,
                payload=payload,
                fields=_fields,
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
