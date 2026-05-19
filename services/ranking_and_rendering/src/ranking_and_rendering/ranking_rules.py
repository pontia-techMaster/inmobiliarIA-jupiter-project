from shared.constants import PRICE_RELAXATION_COEFFICIENT, SURFACE_RELAXATION_COEFFICIENT
from shared.location_utils import ResolvedLocation, resolve_location
from shared.schemas import PromptField


def _compute_location_score(payload: dict, field: PromptField) -> float:

    def score_single_location(payload: dict, resolved: ResolvedLocation) -> float:
        if resolved.type == "neighborhood":
            if payload["neighborhood"] == resolved.value:
                return 1.0
            elif payload["district"] == resolved.parent_district:
                return 0.5
            return 0.0
        else:  # district
            return 1.0 if payload["district"] == resolved.value else 0.0

    if field.strength == "hard":
        # no need to compute because applied in filters
        return 1.0

    resolved_locations = [resolve_location(v) for v in field.value]
    if not resolved_locations:
        return 1.0  # no penalty

    scores = []
    for resolved in resolved_locations:
        if resolved is not None:
            scores.append(score_single_location(payload, resolved))

    return max(scores or [0.0])


def _compute_rooms_score(payload: dict, field: PromptField) -> float:

    if field.strength == "hard":
        return 1.0

    value = payload.get("rooms")
    if value is None:
        return 0.0

    requested: int = min(field.value)  # type: ignore

    if value >= requested:
        return 1.0

    return 0.5


def _compute_bathrooms_score(payload: dict, field: PromptField) -> float:

    if field.strength == "hard":
        return 1.0

    value = payload.get("bathrooms")
    if value is None:
        return 0.0

    requested: int = min(field.value)  # type: ignore

    if value >= requested:
        return 1.0

    return 0.5


def _compute_surface_score(payload: dict, field: PromptField) -> float:

    if field.strength == "hard":
        return 1.0

    value = payload.get("surface")
    if value is None:
        return 0.0

    requested_original: int = min(field.value)  # type: ignore

    if value >= requested_original:
        return 1.0

    shortfall = (requested_original - value) / requested_original
    return 1.0 - (shortfall / SURFACE_RELAXATION_COEFFICIENT) * 0.5


def _compute_price_score(payload: dict, field: PromptField) -> float:

    if field.strength == "hard":
        return 1.0

    value = payload.get("price")
    if value is None:
        return 0.0

    requested_original: int = max(field.value)  # type: ignore
    requested_relaxed = int(requested_original * (1 + PRICE_RELAXATION_COEFFICIENT))

    if value <= requested_original:
        return 1.0

    overshoot = (value - requested_original) / (requested_relaxed - requested_original)
    return max(0.0, 1.0 - overshoot**0.7)


def _compute_has_elevator_score(payload: dict, field: PromptField) -> float:

    if field.strength == "hard":
        return 1.0

    value = bool(payload.get("has_elevator"))
    if value is None:
        return 0.0

    requested: bool = all(field.value)

    if not value and requested:
        return 0.0

    return 1.0


def _compute_is_exterior_score(payload: dict, field: PromptField) -> float:

    if field.strength == "hard":
        return 1.0

    value = bool(payload.get("is_exterior"))
    if value is None:
        return 0.0

    requested: bool = all(field.value)

    if not value and requested:
        return 0.0

    return 1.0
