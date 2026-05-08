from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from process_user_prompt import handler
from shared.schemas import (
    ProcessUserPromptOutput,
    ProcessUserPromptResponse,
    SearchRequest,
)


def test_handle_success(monkeypatch):
    req = SearchRequest(
        request_id="req-123",
        prompt="Busco piso en Madrid con ascensor por menos de 200000 euros",
        user_id="user-1",
    )

    fake_llm_output = ProcessUserPromptOutput(
        fields=[
            {
                "name": "property_type",
                "value": ["apartment"],
                "strength": "soft",
                "extraction_context": "piso",
            },
            {
                "name": "location",
                "value": ["Madrid"],
                "strength": "soft",
                "extraction_context": "en Madrid",
            },
            {
                "name": "has_elevator",
                "value": [True],
                "strength": "soft",
                "extraction_context": "con ascensor",
            },
            {
                "name": "price",
                "value": [200000],
                "strength": "soft",
                "extraction_context": "menos de 200000 euros",
            },
        ],
        extra_info="",
    )

    mock_extract_data = MagicMock(return_value=fake_llm_output)

    monkeypatch.setattr(
        handler,
        "extract_data",
        mock_extract_data,
    )

    result = handler.handle(req)

    assert isinstance(result, ProcessUserPromptResponse)

    assert result.request_id == "req-123"
    assert result.prompt == "Busco piso en Madrid con ascensor por menos de 200000 euros"
    assert result.extra_info == ""

    assert len(result.fields) == 4

    assert result.fields[0].name == "property_type"
    assert result.fields[0].value == ["apartment"]
    assert result.fields[0].strength == "soft"
    assert result.fields[0].extraction_context == "piso"

    assert result.fields[1].name == "location"
    assert result.fields[1].value == ["Madrid"]

    assert result.fields[2].name == "has_elevator"
    assert result.fields[2].value == [True]

    assert result.fields[3].name == "price"
    assert result.fields[3].value == [200000]

    mock_extract_data.assert_called_once_with(
        user_input="Busco piso en Madrid con ascensor por menos de 200000 euros"
    )


def test_handle_with_empty_fields(monkeypatch):
    req = SearchRequest(
        request_id="req-456",
        prompt="Quiero algo luminoso, tranquilo y cerca de zonas verdes",
    )

    fake_llm_output = ProcessUserPromptOutput(
        fields=[],
        extra_info="Vivienda luminosa en entorno tranquilo, próxima a zonas verdes.",
    )

    mock_extract_data = MagicMock(return_value=fake_llm_output)

    monkeypatch.setattr(
        handler,
        "extract_data",
        mock_extract_data,
    )

    result = handler.handle(req)

    assert isinstance(result, ProcessUserPromptResponse)

    assert result.request_id == "req-456"
    assert result.prompt == "Quiero algo luminoso, tranquilo y cerca de zonas verdes"
    assert result.fields == []
    assert result.extra_info == (
        "Vivienda luminosa en entorno tranquilo, próxima a zonas verdes."
    )

    mock_extract_data.assert_called_once_with(
        user_input="Quiero algo luminoso, tranquilo y cerca de zonas verdes"
    )


def test_handle_does_not_include_user_id_in_response(monkeypatch):
    req = SearchRequest(
        request_id="req-789",
        prompt="Busco casa con jardín",
        user_id="user-999",
    )

    fake_llm_output = ProcessUserPromptOutput(
        fields=[
            {
                "name": "property_type",
                "value": ["house"],
                "strength": "soft",
                "extraction_context": "casa",
            }
        ],
        extra_info="Vivienda con jardín.",
    )

    mock_extract_data = MagicMock(return_value=fake_llm_output)

    monkeypatch.setattr(
        handler,
        "extract_data",
        mock_extract_data,
    )

    result = handler.handle(req)

    assert result.request_id == "req-789"
    assert result.prompt == "Busco casa con jardín"
    assert result.extra_info == "Vivienda con jardín."

    assert not hasattr(result, "user_id")

    mock_extract_data.assert_called_once_with(
        user_input="Busco casa con jardín"
    )


def test_handle_propagates_extract_data_error(monkeypatch):
    req = SearchRequest(
        request_id="req-error",
        prompt="Busco piso barato",
    )

    mock_extract_data = MagicMock(
        side_effect=RuntimeError("LLM extraction failed")
    )

    monkeypatch.setattr(
        handler,
        "extract_data",
        mock_extract_data,
    )

    with pytest.raises(RuntimeError, match="LLM extraction failed"):
        handler.handle(req)

    mock_extract_data.assert_called_once_with(
        user_input="Busco piso barato"
    )


def test_handle_raises_validation_error_when_llm_output_is_invalid(monkeypatch):
    req = SearchRequest(
        request_id="req-invalid",
        prompt="Busco castillo medieval en Marte",
    )

    invalid_output = MagicMock()
    invalid_output.model_dump.return_value = {
        "fields": [
            {
                "name": "invalid_field",
                "value": ["whatever"],
                "strength": "soft",
                "extraction_context": "castillo medieval",
            }
        ],
        "extra_info": "Solicitud no estándar.",
    }

    mock_extract_data = MagicMock(return_value=invalid_output)

    monkeypatch.setattr(
        handler,
        "extract_data",
        mock_extract_data,
    )

    with pytest.raises(ValidationError):
        handler.handle(req)

    mock_extract_data.assert_called_once_with(
        user_input="Busco castillo medieval en Marte"
    )