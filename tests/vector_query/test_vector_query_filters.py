import pytest
from qdrant_client.models import Filter, MatchAny, MatchValue
from shared.schemas import PromptField
from vector_query.filters import build


def make_field(name, value, strength="soft", context="test context"):
    return PromptField(
        name=name,
        value=value,
        strength=strength,
        extraction_context=context,
    )


def test_build_returns_none_when_no_fields():
    result = build([])

    assert result is None


def test_build_property_type_single_value_uses_match_value():
    fields = [
        make_field(
            name="property_type",
            value=["apartment"],
            context="piso",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "property_type"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == "apartment"


def test_build_property_type_multiple_values_uses_match_any():
    fields = [
        make_field(
            name="property_type",
            value=["apartment", "house"],
            context="piso o casa",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "property_type"
    assert isinstance(condition.match, MatchAny)
    assert condition.match.any == ["apartment", "house"]


def test_build_location_single_value_uses_match_value():
    fields = [
        make_field(
            name="location",
            value=["Madrid"],
            context="en Madrid",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "location"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == "Madrid"


def test_build_location_multiple_values_uses_match_any():
    fields = [
        make_field(
            name="location",
            value=["Madrid", "Salamanca"],
            context="Madrid o Salamanca",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "location"
    assert isinstance(condition.match, MatchAny)
    assert condition.match.any == ["Madrid", "Salamanca"]


def test_build_has_elevator_true_uses_match_value():
    fields = [
        make_field(
            name="has_elevator",
            value=[True],
            context="con ascensor",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "has_elevator"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value is True


def test_build_has_elevator_false_uses_match_value():
    fields = [
        make_field(
            name="has_elevator",
            value=[False],
            context="sin ascensor",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "has_elevator"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value is False


def test_build_is_exterior_true_uses_match_value():
    fields = [
        make_field(
            name="is_exterior",
            value=[True],
            context="exterior",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "is_exterior"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value is True


def test_build_price_uses_max_value():
    fields = [
        make_field(
            name="price",
            value=[150000, 200000],
            context="entre 150000 y 200000",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "price"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == 200000


def test_build_rooms_uses_min_value():
    fields = [
        make_field(
            name="rooms",
            value=[3, 4],
            context="3 o 4 habitaciones",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "rooms"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == 3


def test_build_bathrooms_uses_min_value():
    fields = [
        make_field(
            name="bathrooms",
            value=[2, 3],
            context="2 o 3 baños",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "bathrooms"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == 2


def test_build_surface_uses_min_value():
    fields = [
        make_field(
            name="surface",
            value=[80, 100],
            context="80 o 100 metros",
        )
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 1

    condition = result.must[0]

    assert condition.key == "surface"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == 80


def test_build_multiple_fields_generates_multiple_must_conditions():
    fields = [
        make_field("property_type", ["apartment"], context="piso"),
        make_field("location", ["Madrid"], context="Madrid"),
        make_field("has_elevator", [True], context="ascensor"),
        make_field("price", [200000], context="menos de 200000"),
    ]

    result = build(fields)

    assert isinstance(result, Filter)
    assert len(result.must) == 4

    keys = [condition.key for condition in result.must]

    assert keys == [
        "property_type",
        "location",
        "has_elevator",
        "price",
    ]


def test_build_price_with_empty_value_raises_error():
    fields = [
        make_field(
            name="price",
            value=[],
            context="sin precio",
        )
    ]

    with pytest.raises(ValueError):
        build(fields)
