import pytest
from pydantic import ValidationError
from shared.schemas import (
    ProcessUserPromptOutput,
    ProcessUserPromptResponse,
    PromptField,
    SearchRequest,
)


def test_search_request_valid():
    request = SearchRequest(
        request_id="req-123",
        prompt="Busco piso en Madrid",
        user_id="user-1",
    )

    assert request.request_id == "req-123"
    assert request.prompt == "Busco piso en Madrid"
    assert request.user_id == "user-1"


def test_search_request_without_user_id():
    request = SearchRequest(
        request_id="req-123",
        prompt="Busco piso en Madrid",
    )

    assert request.request_id == "req-123"
    assert request.prompt == "Busco piso en Madrid"
    assert request.user_id is None


def test_search_request_requires_request_id():
    with pytest.raises(ValidationError):
        SearchRequest(
            prompt="Busco piso en Madrid",
        )


def test_search_request_requires_prompt():
    with pytest.raises(ValidationError):
        SearchRequest(
            request_id="req-123",
        )


def test_prompt_field_valid():
    field = PromptField(
        name="price",
        value=[200000],
        strength="soft",
        extraction_context="menos de 200000 euros",
    )

    assert field.name == "price"
    assert field.value == [200000]
    assert field.strength == "soft"
    assert field.extraction_context == "menos de 200000 euros"


def test_prompt_field_accepts_boolean_value():
    field = PromptField(
        name="has_elevator",
        value=[True],
        strength="hard",
        extraction_context="imprescindible que tenga ascensor",
    )

    assert field.name == "has_elevator"
    assert field.value == [True]
    assert field.strength == "hard"


def test_prompt_field_accepts_multiple_values():
    field = PromptField(
        name="property_type",
        value=["apartment", "house"],
        strength="soft",
        extraction_context="me da igual piso o casa",
    )

    assert field.name == "property_type"
    assert field.value == ["apartment", "house"]
    assert field.strength == "soft"


def test_prompt_field_rejects_invalid_name():
    with pytest.raises(ValidationError):
        PromptField(
            name="garage",
            value=[True],
            strength="soft",
            extraction_context="con garaje",
        )


def test_prompt_field_rejects_invalid_strength():
    with pytest.raises(ValidationError):
        PromptField(
            name="price",
            value=[200000],
            strength="medium",
            extraction_context="menos de 200000 euros",
        )


def test_prompt_field_rejects_value_that_is_not_list():
    with pytest.raises(ValidationError):
        PromptField(
            name="price",
            value=200000,
            strength="soft",
            extraction_context="menos de 200000 euros",
        )


def test_process_user_prompt_output_valid():
    output = ProcessUserPromptOutput(
        fields=[
            {
                "name": "rooms",
                "value": [3],
                "strength": "soft",
                "extraction_context": "3 habitaciones",
            }
        ],
        extra_info="Vivienda luminosa.",
    )

    assert len(output.fields) == 1
    assert output.fields[0].name == "rooms"
    assert output.fields[0].value == [3]
    assert output.extra_info == "Vivienda luminosa."


def test_process_user_prompt_output_without_fields():
    output = ProcessUserPromptOutput(
        extra_info="Vivienda luminosa en zona tranquila.",
    )

    assert output.fields == []
    assert output.extra_info == "Vivienda luminosa en zona tranquila."


def test_process_user_prompt_output_requires_extra_info():
    with pytest.raises(ValidationError):
        ProcessUserPromptOutput(
            fields=[],
        )


def test_process_user_prompt_response_valid():
    response = ProcessUserPromptResponse(
        request_id="req-123",
        prompt="Busco piso en Madrid",
        fields=[
            {
                "name": "location",
                "value": ["Madrid"],
                "strength": "soft",
                "extraction_context": "en Madrid",
            }
        ],
        extra_info="",
    )

    assert response.request_id == "req-123"
    assert response.prompt == "Busco piso en Madrid"
    assert len(response.fields) == 1
    assert response.fields[0].name == "location"
    assert response.extra_info == ""


def test_process_user_prompt_response_without_fields():
    response = ProcessUserPromptResponse(
        request_id="req-123",
        prompt="Quiero algo luminoso",
        extra_info="Vivienda luminosa.",
    )

    assert response.request_id == "req-123"
    assert response.prompt == "Quiero algo luminoso"
    assert response.fields == []
    assert response.extra_info == "Vivienda luminosa."


def test_process_user_prompt_response_requires_request_id():
    with pytest.raises(ValidationError):
        ProcessUserPromptResponse(
            prompt="Busco piso en Madrid",
            fields=[],
            extra_info="",
        )


def test_process_user_prompt_response_requires_prompt():
    with pytest.raises(ValidationError):
        ProcessUserPromptResponse(
            request_id="req-123",
            fields=[],
            extra_info="",
        )
