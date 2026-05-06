"""
Ranking rules.

This module contains the rules that modify the score of a property
based on the fields provided by the user.

The idea is to separate the scoring logic from the sorting process.
This way, if we add more fields in the future, we don't have to modify the rank() function.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from shared.schemas import PromptField


def clean_field_values(values: list[str | int | bool], key: str) -> Any:
    match key:
        case "price":
            return max(values)
        case "has_elevator" | "is_exterior":
            return all(values)
        case "rooms":
            return min(values)
        case _:
            return values


class RankingRule(Protocol):
    """
    Common interface for any ranking rule.

    Each rule receives:
    - current score
    - document payload
    - user fields

    And returns:
    - modified score
    """

    def apply(
        self,
        score: float,
        payload: dict[str, Any],
        fields: dict[str, PromptField],
    ) -> float: ...


def is_empty(value: Any) -> bool:
    """
    Checks if a filter should be considered empty.

    Important:
    - None is considered empty.
    - "" is considered empty.
    - [] is considered empty.
    - False is NOT considered empty, as it can be a valid boolean filter.
    """

    if value is None:
        return True

    if isinstance(value, str) and value.strip() == "":
        return True

    if isinstance(value, list) and len(value) == 0:
        return True

    return False


def normalize(value: Any) -> str:
    """
    Normalizes text for comparison, ignoring case and spaces.
    """

    return str(value).strip().lower()


def to_float(value: Any) -> float | None:
    """
    Safely converts numeric values to float.

    If conversion fails, returns None.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ExactMatchRule:
    """
    Rule for exact match fields.

    Used for fields like:
    - property_type
    """

    filter_key: str
    payload_key: str
    bonus: float
    penalty: float

    def apply(
        self,
        score: float,
        payload: dict[str, Any],
        fields: dict[str, PromptField],
    ) -> float:
        field = fields.get(self.filter_key)
        if field is None:
            return score
        expected_value = clean_field_values(field.value, self.filter_key)

        actual = payload.get(self.payload_key)

        if is_empty(expected_value) or is_empty(actual):
            return score

        if normalize(actual) == normalize(expected_value):
            return score + self.bonus

        return score - self.penalty


@dataclass
class MinValueRule:
    """
    Rule for minimum value fields.

    Penalizes if the actual value is below the requested minimum.

    Examples:
    - rooms
    """

    filter_key: str
    payload_key: str
    penalty: float

    def apply(
        self,
        score: float,
        payload: dict[str, Any],
        fields: dict[str, PromptField],
    ) -> float:
        field = fields.get(self.filter_key)
        if field is None:
            return score
        expected_value = clean_field_values(field.value, self.filter_key)
        actual = to_float(payload.get(self.payload_key))

        if expected_value is None or actual is None:
            return score

        if actual < expected_value:
            return score - self.penalty

        return score


@dataclass
class MaxValueRule:
    """
    Rule for maximum value fields.

    Penalizes if the actual value exceeds the requested maximum.

    Examples:
    - price
    """

    filter_key: str
    payload_key: str
    penalty: float

    def apply(
        self,
        score: float,
        payload: dict[str, Any],
        fields: dict[str, PromptField],
    ) -> float:
        field = fields.get(self.filter_key)
        if field is None:
            return score
        expected_value = clean_field_values(field.value, self.filter_key)
        actual = to_float(payload.get(self.payload_key))

        if expected_value is None or actual is None:
            return score

        if actual > expected_value:
            return score - self.penalty

        return score


@dataclass
class BooleanMatchRule:
    """
    Rule for boolean fields.

    Used for fields like:
    - is_exterior
    - has_elevator
    """

    filter_key: str
    payload_key: str
    bonus: float
    penalty: float

    def apply(
        self,
        score: float,
        payload: dict[str, Any],
        fields: dict[str, PromptField],
    ) -> float:
        field = fields.get(self.filter_key)
        if field is None:
            return score
        expected_value = clean_field_values(field.value, self.filter_key)
        actual = payload.get(self.payload_key)

        if expected_value is None or actual is None:
            return score

        if actual == expected_value:
            return score + self.bonus

        return score - self.penalty


# @dataclass
# class FloorMatchRule:
#     """
#     Rule specific to the floor filter, which can be either a single value or a list of values.

#     Allows two forms:
#     floor = "2"
#     and: floor = ["1", "2", "3"]
#     """

#     filter_key: str = "floor"
#     payload_key: str = "floor"
#     bonus: float = 0.2
#     penalty: float = 0.1

#     def apply(
#         self,
#         score: float,
#         payload: dict[str, Any],
#         fields: dict[str, PromptField],
#     ) -> float:
#         expected = fields.name
#         actual = payload.get(self.payload_key)

#         if is_empty(expected) or is_empty(actual):
#             return score

#         actual_normalized = normalize(actual)

#         if isinstance(expected, list):
#             accepted_values = [normalize(value) for value in expected]

#             if actual_normalized in accepted_values:
#                 return score + self.bonus

#             return score - self.penalty

#         if actual_normalized == normalize(expected):
#             return score + self.bonus

#         return score - self.penalty


RANKING_RULES: list[RankingRule] = [
    # location fields with exact match and penalties and bonuses
    # ExactMatchRule(
    #     filter_key="city",
    #     payload_key="city",
    #     bonus=0.5,
    #     penalty=0.2,
    # ),
    # ExactMatchRule(
    #     filter_key="neighborhood",
    #     payload_key="neighborhood",
    #     bonus=0.3,
    #     penalty=0.1,
    # ),
    # ExactMatchRule(
    #     filter_key="district",
    #     payload_key="district",
    #     bonus=0.2,
    #     penalty=0.1,
    # ),
    # # price filter
    # MaxValueRule(
    #     filter_key="max_price",
    #     payload_key="price",
    #     penalty=0.3,
    # ),
    # MinValueRule(
    #     filter_key="min_price",
    #     payload_key="price",
    #     penalty=0.1,
    # ),
    # # superface filter
    # MinValueRule(
    #     filter_key="min_surface",
    #     payload_key="surface",
    #     penalty=0.2,
    # ),
    # MaxValueRule(
    #     filter_key="max_surface",
    #     payload_key="surface",
    #     penalty=0.2,
    # ),
    # # rooms and bathrooms fields
    # MinValueRule(
    #     filter_key="min_rooms",
    #     payload_key="rooms",
    #     penalty=0.2,
    # ),
    # MinValueRule(
    #     filter_key="min_bathrooms",
    #     payload_key="bathrooms",
    #     penalty=0.2,
    # ),
    # # type and subtype of property fields
    ExactMatchRule(
        filter_key="property_type",
        payload_key="property_type",
        bonus=0.3,
        penalty=0.2,
    ),
    # ExactMatchRule(
    #     filter_key="property_subtype",
    #     payload_key="property_subtype",
    #     bonus=0.2,
    #     penalty=0.1,
    # ),
    # # floor filter with special logic to handle both single value and list of values
    # FloorMatchRule(),
    # boolean fields
    BooleanMatchRule(
        filter_key="is_exterior",
        payload_key="is_exterior",
        bonus=0.3,
        penalty=0.3,
    ),
    BooleanMatchRule(
        filter_key="has_elevator",
        payload_key="has_elevator",
        bonus=0.3,
        penalty=0.3,
    ),
    MaxValueRule(
        filter_key="price",
        payload_key="price",
        penalty=0.3,
    ),
    MinValueRule(
        filter_key="rooms",
        payload_key="rooms",
        penalty=0.3,
    ),
]
