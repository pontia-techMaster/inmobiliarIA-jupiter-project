from ranking_and_rendering.ranking_rules import (
    _compute_bathrooms_score,
    _compute_has_elevator_score,
    _compute_is_exterior_score,
    _compute_location_score,
    _compute_price_score,
    _compute_rooms_score,
    _compute_surface_score,
)
from shared.schemas import PromptField


def _field(name: str, value: list, strength: str = "soft") -> PromptField:
    return PromptField(
        name=name,
        value=value,
        strength=strength,
        extraction_context="test context",
    )


# location score


def test_location_hard_returns_full_score():
    payload = {
        "district": "Centro",
        "neighborhood": "Sol",
    }

    field = _field("location", ["Sol"], "hard")

    assert _compute_location_score(payload, field) == 1.0


def test_location_soft_exact_neighborhood_returns_full_score():
    payload = {
        "district": "Centro",
        "neighborhood": "Sol",
    }

    field = _field("location", ["Sol"], "soft")

    assert _compute_location_score(payload, field) == 1.0


def test_location_soft_same_parent_district_returns_partial_score():
    payload = {
        "district": "Centro",
        "neighborhood": "Palacio",
    }

    field = _field("location", ["Sol"], "soft")

    assert _compute_location_score(payload, field) == 0.5


def test_location_soft_different_district_returns_zero():
    payload = {
        "district": "Retiro",
        "neighborhood": "Ibiza",
    }

    field = _field("location", ["Sol"], "soft")

    assert _compute_location_score(payload, field) == 0.0


def test_location_soft_district_match_returns_full_score():
    payload = {
        "district": "Centro",
        "neighborhood": "Palacio",
    }

    field = _field("location", ["Centro"], "soft")

    assert _compute_location_score(payload, field) == 1.0


def test_location_soft_district_mismatch_returns_zero():
    payload = {
        "district": "Retiro",
        "neighborhood": "Ibiza",
    }

    field = _field("location", ["Centro"], "soft")

    assert _compute_location_score(payload, field) == 0.0


def test_location_soft_unknown_location_returns_zero():
    payload = {
        "district": "Centro",
        "neighborhood": "Sol",
    }

    field = _field("location", ["Lugar inventado que no existe"], "soft")

    assert _compute_location_score(payload, field) == 0.0


def test_location_soft_empty_values_returns_full_score():
    payload = {
        "district": "Centro",
        "neighborhood": "Sol",
    }

    field = _field("location", [], "soft")

    assert _compute_location_score(payload, field) == 1.0


# rooms score


def test_rooms_hard_returns_full_score():
    payload = {"rooms": 1}
    field = _field("rooms", [3], "hard")

    assert _compute_rooms_score(payload, field) == 1.0


def test_rooms_soft_missing_value_returns_zero():
    payload = {}
    field = _field("rooms", [3], "soft")

    assert _compute_rooms_score(payload, field) == 0.0


def test_rooms_soft_enough_rooms_returns_full_score():
    payload = {"rooms": 3}
    field = _field("rooms", [3], "soft")

    assert _compute_rooms_score(payload, field) == 1.0


def test_rooms_soft_below_requested_returns_partial_score():
    payload = {"rooms": 2}
    field = _field("rooms", [3], "soft")

    assert _compute_rooms_score(payload, field) == 0.5


# bathrooms score


def test_bathrooms_hard_returns_full_score():
    payload = {"bathrooms": 1}
    field = _field("bathrooms", [2], "hard")

    assert _compute_bathrooms_score(payload, field) == 1.0


def test_bathrooms_soft_missing_value_returns_zero():
    payload = {}
    field = _field("bathrooms", [2], "soft")

    assert _compute_bathrooms_score(payload, field) == 0.0


def test_bathrooms_soft_enough_bathrooms_returns_full_score():
    payload = {"bathrooms": 2}
    field = _field("bathrooms", [2], "soft")

    assert _compute_bathrooms_score(payload, field) == 1.0


def test_bathrooms_soft_below_requested_returns_partial_score():
    payload = {"bathrooms": 1}
    field = _field("bathrooms", [2], "soft")

    assert _compute_bathrooms_score(payload, field) == 0.5


# surface score


def test_surface_hard_returns_full_score():
    payload = {"surface": 40}
    field = _field("surface", [80], "hard")

    assert _compute_surface_score(payload, field) == 1.0


def test_surface_soft_missing_value_returns_zero():
    payload = {}
    field = _field("surface", [80], "soft")

    assert _compute_surface_score(payload, field) == 0.0


def test_surface_soft_enough_surface_returns_full_score():
    payload = {"surface": 85}
    field = _field("surface", [80], "soft")

    assert _compute_surface_score(payload, field) == 1.0


def test_surface_soft_below_requested_penalizes():
    payload = {"surface": 70}
    field = _field("surface", [80], "soft")

    assert 0.0 < _compute_surface_score(payload, field) < 1.0


# price score


def test_price_hard_returns_full_score():
    payload = {"price": 300000}
    field = _field("price", [200000], "hard")

    assert _compute_price_score(payload, field) == 1.0


def test_price_soft_missing_value_returns_zero():
    payload = {}
    field = _field("price", [200000], "soft")

    assert _compute_price_score(payload, field) == 0.0


def test_price_soft_within_requested_returns_full_score():
    payload = {"price": 190000}
    field = _field("price", [200000], "soft")

    assert _compute_price_score(payload, field) == 1.0


def test_price_soft_above_requested_penalizes():
    payload = {"price": 210000}
    field = _field("price", [200000], "soft")

    assert 0.0 < _compute_price_score(payload, field) < 1.0


def test_price_soft_far_above_relaxed_limit_returns_zero():
    payload = {"price": 400000}
    field = _field("price", [200000], "soft")

    assert _compute_price_score(payload, field) == 0.0


# elevator score


def test_has_elevator_hard_returns_full_score():
    payload = {"has_elevator": False}
    field = _field("has_elevator", [True], "hard")

    assert _compute_has_elevator_score(payload, field) == 1.0


def test_has_elevator_soft_missing_or_false_requested_true_returns_zero():
    payload = {}
    field = _field("has_elevator", [True], "soft")

    assert _compute_has_elevator_score(payload, field) == 0.0


def test_has_elevator_soft_false_when_requested_true_returns_zero():
    payload = {"has_elevator": False}
    field = _field("has_elevator", [True], "soft")

    assert _compute_has_elevator_score(payload, field) == 0.0


def test_has_elevator_soft_true_when_requested_true_returns_full_score():
    payload = {"has_elevator": True}
    field = _field("has_elevator", [True], "soft")

    assert _compute_has_elevator_score(payload, field) == 1.0


def test_has_elevator_soft_false_when_not_required_returns_full_score():
    payload = {"has_elevator": False}
    field = _field("has_elevator", [False], "soft")

    assert _compute_has_elevator_score(payload, field) == 1.0


# is exterior score


def test_is_exterior_hard_returns_full_score():
    payload = {"is_exterior": False}
    field = _field("is_exterior", [True], "hard")

    assert _compute_is_exterior_score(payload, field) == 1.0


def test_is_exterior_soft_missing_or_false_requested_true_returns_zero():
    payload = {}
    field = _field("is_exterior", [True], "soft")

    assert _compute_is_exterior_score(payload, field) == 0.0


def test_is_exterior_soft_false_when_requested_true_returns_zero():
    payload = {"is_exterior": False}
    field = _field("is_exterior", [True], "soft")

    assert _compute_is_exterior_score(payload, field) == 0.0


def test_is_exterior_soft_true_when_requested_true_returns_full_score():
    payload = {"is_exterior": True}
    field = _field("is_exterior", [True], "soft")

    assert _compute_is_exterior_score(payload, field) == 1.0


def test_is_exterior_soft_false_when_not_required_returns_full_score():
    payload = {"is_exterior": False}
    field = _field("is_exterior", [False], "soft")

    assert _compute_is_exterior_score(payload, field) == 1.0
