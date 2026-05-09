from __future__ import annotations

import sys
from unittest.mock import patch

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

sys.path.append("services/vector_query/src")
from shared.schemas import PromptField
from vector_query.filters import (
    _BATHROOMS_RELAXATION_COEFFICIENT,
    _PRICE_RELAXATION_COEFFICIENT,
    _ROOMS_RELAXATION_COEFFICIENT,
    _SURFACE_RELAXATION_COEFFICIENT,
    _build_bathrooms_filter,
    _build_has_elevator_filter,
    _build_is_exterior_filter,
    _build_location_filter,
    _build_price_filter,
    _build_property_type_filter,
    _build_rooms_filter,
    _build_surface_filter,
    build,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_range(conditions: list[FieldCondition], key: str) -> Range:
    return next(c.range for c in conditions if c.key == key)  # type: ignore


def _get_match_any(conditions: list[FieldCondition], key: str) -> MatchAny:
    return next(c.match for c in conditions if c.key == key)  # type: ignore


def _get_match_value(conditions: list[FieldCondition], key: str) -> MatchValue:
    return next(c.match for c in conditions if c.key == key)  # type: ignore


# ---------------------------------------------------------------------------
# _build_property_type_filter
# ---------------------------------------------------------------------------


class TestBuildPropertyTypeFilter:

    def test_single_value_hard(self):
        result = _build_property_type_filter(["apartment"], "hard")
        assert len(result) == 1
        assert _get_match_any(result, "property_type").any == ["apartment"]

    def test_single_value_soft(self):
        # property_type ignora strength, mismo comportamiento
        result = _build_property_type_filter(["apartment"], "soft")
        assert _get_match_any(result, "property_type").any == ["apartment"]

    def test_multiple_values(self):
        result = _build_property_type_filter(["apartment", "house"], "hard")
        assert set(_get_match_any(result, "property_type").any) == {"apartment", "house"}


# ---------------------------------------------------------------------------
# _build_rooms_filter
# ---------------------------------------------------------------------------


class TestBuildRoomsFilter:

    def test_hard_uses_exact_min(self):
        result = _build_rooms_filter([3], "hard")
        assert _get_range(result, "rooms").gte == 3

    def test_soft_relaxes_by_coefficient(self):
        result = _build_rooms_filter([3], "soft")
        assert _get_range(result, "rooms").gte == 3 - _ROOMS_RELAXATION_COEFFICIENT

    def test_soft_floor_at_one(self):
        result = _build_rooms_filter([1], "soft")
        assert _get_range(result, "rooms").gte == 1

    def test_uses_min_when_multiple_values(self):
        # Si el LLM devuelve rango [2, 4], el filtro usa el mínimo
        result = _build_rooms_filter([2, 4], "hard")
        assert _get_range(result, "rooms").gte == 2

    def test_no_upper_bound(self):
        result = _build_rooms_filter([3], "hard")
        assert _get_range(result, "rooms").lte is None


# ---------------------------------------------------------------------------
# _build_bathrooms_filter
# ---------------------------------------------------------------------------


class TestBuildBathroomsFilter:

    def test_hard_uses_exact_min(self):
        result = _build_bathrooms_filter([2], "hard")
        assert _get_range(result, "bathrooms").gte == 2

    def test_soft_relaxes_by_coefficient(self):
        result = _build_bathrooms_filter([2], "soft")
        assert _get_range(result, "bathrooms").gte == 2 - _BATHROOMS_RELAXATION_COEFFICIENT

    def test_soft_floor_at_one(self):
        result = _build_bathrooms_filter([1], "soft")
        assert _get_range(result, "bathrooms").gte == 1


# ---------------------------------------------------------------------------
# _build_surface_filter
# ---------------------------------------------------------------------------


class TestBuildSurfaceFilter:

    def test_hard_uses_exact_min(self):
        result = _build_surface_filter([80], "hard")
        assert _get_range(result, "surface").gte == 80

    def test_soft_relaxes_by_percentage(self):
        result = _build_surface_filter([80], "soft")
        expected = int(80 * (1 - _SURFACE_RELAXATION_COEFFICIENT))
        assert _get_range(result, "surface").gte == expected

    def test_soft_relaxation_rounds_down(self):
        # 75 * 0.85 = 63.75 → int = 63
        result = _build_surface_filter([75], "soft")
        assert _get_range(result, "surface").gte == int(75 * (1 - _SURFACE_RELAXATION_COEFFICIENT))

    def test_uses_min_when_multiple_values(self):
        result = _build_surface_filter([60, 120], "hard")
        assert _get_range(result, "surface").gte == 60


# ---------------------------------------------------------------------------
# _build_price_filter
# ---------------------------------------------------------------------------


class TestBuildPriceFilter:

    def test_hard_uses_exact_max(self):
        result = _build_price_filter([200_000], "hard")
        assert _get_range(result, "price").lte == 200_000

    def test_soft_relaxes_upward_by_percentage(self):
        result = _build_price_filter([200_000], "soft")
        expected = int(200_000 * (1 + _PRICE_RELAXATION_COEFFICIENT))
        assert _get_range(result, "price").lte == expected

    def test_no_lower_bound(self):
        result = _build_price_filter([200_000], "hard")
        assert _get_range(result, "price").gte is None

    def test_uses_max_when_multiple_values(self):
        result = _build_price_filter([150_000, 200_000], "hard")
        assert _get_range(result, "price").lte == 200_000


# ---------------------------------------------------------------------------
# _build_has_elevator_filter
# ---------------------------------------------------------------------------


class TestBuildHasElevatorFilter:

    def test_true_value(self):
        result = _build_has_elevator_filter([True], "hard")
        assert _get_match_value(result, "has_elevator").value is True

    def test_false_value(self):
        result = _build_has_elevator_filter([False], "hard")
        assert _get_match_value(result, "has_elevator").value is False

    def test_all_must_be_true_for_true(self):
        # all([True, True]) → True
        result = _build_has_elevator_filter([True, True], "soft")
        assert _get_match_value(result, "has_elevator").value is True

    def test_any_false_yields_false(self):
        # all([True, False]) → False
        result = _build_has_elevator_filter([True, False], "soft")
        assert _get_match_value(result, "has_elevator").value is False

    def test_strength_does_not_affect_boolean(self):
        hard = _build_has_elevator_filter([True], "hard")
        soft = _build_has_elevator_filter([True], "soft")
        assert _get_match_value(hard, "has_elevator").value == _get_match_value(soft, "has_elevator").value


# ---------------------------------------------------------------------------
# _build_is_exterior_filter
# ---------------------------------------------------------------------------


class TestBuildIsExteriorFilter:

    def test_true_value(self):
        result = _build_is_exterior_filter([True], "hard")
        assert _get_match_value(result, "is_exterior").value is True

    def test_false_value(self):
        result = _build_is_exterior_filter([False], "soft")
        assert _get_match_value(result, "is_exterior").value is False


# ---------------------------------------------------------------------------
# _build_location_filter
# ---------------------------------------------------------------------------

MOCK_DISTRICT = {"type": "district", "value": "Centro", "parent_district": None, "score": 95}
MOCK_NEIGHBOURHOOD = {"type": "neighborhood", "value": "Realejo", "parent_district": "Centro", "score": 90}


class TestBuildLocationFilter:

    @patch("vector_query.filters.resolve_location", return_value=MOCK_DISTRICT)
    def test_hard_district_filters_by_district(self, _):
        result = _build_location_filter(["centro"], "hard")
        assert any(c.key == "district" for c in result)
        assert _get_match_any(result, "district").any == ["Centro"]

    @patch("vector_query.filters.resolve_location", return_value=MOCK_NEIGHBOURHOOD)
    def test_hard_neighbourhood_filters_by_neighbourhood(self, _):
        result = _build_location_filter(["realejo"], "hard")
        assert any(c.key == "neighborhood" for c in result)
        assert _get_match_any(result, "neighborhood").any == ["Realejo"]

    @patch("vector_query.filters.resolve_location", return_value=MOCK_NEIGHBOURHOOD)
    def test_soft_neighbourhood_relaxes_to_parent_district(self, _):
        result = _build_location_filter(["realejo"], "soft")
        # Soft → filtra por distrito padre, no por barrio
        assert any(c.key == "district" for c in result)
        assert not any(c.key == "neighborhood" for c in result)
        assert _get_match_any(result, "district").any == ["Centro"]

    @patch("vector_query.filters.resolve_location", return_value=MOCK_DISTRICT)
    def test_soft_district_filters_by_district(self, _):
        result = _build_location_filter(["centro"], "soft")
        assert _get_match_any(result, "district").any == ["Centro"]

    @patch("vector_query.filters.resolve_location", return_value=None)
    def test_unresolved_location_returns_empty(self, _):
        result = _build_location_filter(["lugar_inexistente"], "hard")
        assert result == []

    @patch("vector_query.filters.resolve_location", side_effect=[MOCK_DISTRICT, MOCK_NEIGHBOURHOOD])
    def test_multiple_values_hard(self, _):
        result = _build_location_filter(["centro", "realejo"], "hard")
        keys = [c.key for c in result]
        assert "district" in keys
        assert "neighborhood" in keys


# ---------------------------------------------------------------------------
# build (integración)
# ---------------------------------------------------------------------------


def _make_field(name: str, value, strength: str = "soft", extraction_context: str = "") -> PromptField:
    return PromptField(name=name, value=value, strength=strength, extraction_context=extraction_context)


class TestBuild:

    def test_returns_none_when_no_fields(self):
        assert build([]) is None

    def test_single_field_returns_filter(self):
        fields = [_make_field("rooms", [3], "hard")]
        result = build(fields)
        assert isinstance(result, Filter)
        assert len(result.must) == 1

    def test_multiple_fields_all_in_must(self):
        fields = [
            _make_field("rooms", [3], "hard"),
            _make_field("price", [200_000], "soft"),
            _make_field("property_type", ["apartment"], "hard"),
        ]
        result = build(fields)
        assert isinstance(result, Filter)
        assert len(result.must) == 3

    def test_soft_rooms_relaxation_applied_in_build(self):
        fields = [_make_field("rooms", [3], "soft")]
        result = build(fields)
        condition: FieldCondition = result.must[0]
        assert condition.range.gte == 3 - _ROOMS_RELAXATION_COEFFICIENT

    def test_hard_price_no_relaxation_in_build(self):
        fields = [_make_field("price", [200_000], "hard")]
        result = build(fields)
        condition: FieldCondition = result.must[0]
        assert condition.range.lte == 200_000

    def test_soft_price_relaxation_applied_in_build(self):
        fields = [_make_field("price", [200_000], "soft")]
        result = build(fields)
        condition: FieldCondition = result.must[0]
        assert condition.range.lte == int(200_000 * (1 + _PRICE_RELAXATION_COEFFICIENT))

    @patch("vector_query.filters.resolve_location", return_value=MOCK_DISTRICT)
    def test_location_integrated_in_build(self, _):
        fields = [_make_field("location", ["centro"], "hard")]
        result = build(fields)
        assert isinstance(result, Filter)
        assert any(isinstance(c, FieldCondition) and c.key == "district" for c in result.must)
