from unittest.mock import MagicMock

import pytest
from process_user_prompt import llm
from shared.schemas import ProcessUserPromptOutput


def test_load_system_prompt_success(tmp_path):
    prompt_file = tmp_path / "system-prompt.md"
    prompt_file.write_text("Eres un experto inmobiliario.", encoding="utf-8")

    result = llm._load_system_prompt(str(prompt_file))

    assert result == "Eres un experto inmobiliario."


def test_load_system_prompt_raises_file_not_found(tmp_path):
    missing_file = tmp_path / "missing-system-prompt.md"

    with pytest.raises(FileNotFoundError):
        llm._load_system_prompt(str(missing_file))


def test_extract_data_success(monkeypatch):
    user_input = "Busco piso en Madrid con ascensor"

    fake_output = ProcessUserPromptOutput(
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
        ],
        extra_info="",
    )

    fake_chain = MagicMock()
    fake_chain.invoke.return_value = fake_output

    mock_create_chain = MagicMock(return_value=fake_chain)

    monkeypatch.setattr(
        llm,
        "_create_chain",
        mock_create_chain,
    )

    result = llm.extract_data(user_input)

    assert result == fake_output

    mock_create_chain.assert_called_once_with(
        model_name=llm.GEMINI_MODEL_NAME,
        temperature=llm.MODEL_TEMPERATURE,
        system_prompt_path=llm.SYSTEM_PROMPT_PATH,
    )

    fake_chain.invoke.assert_called_once_with({"user_input": user_input})


def test_extract_data_propagates_chain_error(monkeypatch):
    user_input = "Busco piso barato"

    fake_chain = MagicMock()
    fake_chain.invoke.side_effect = RuntimeError("Gemini failed")

    mock_create_chain = MagicMock(return_value=fake_chain)

    monkeypatch.setattr(
        llm,
        "_create_chain",
        mock_create_chain,
    )

    with pytest.raises(RuntimeError, match="Gemini failed"):
        llm.extract_data(user_input)

    mock_create_chain.assert_called_once_with(
        model_name=llm.GEMINI_MODEL_NAME,
        temperature=llm.MODEL_TEMPERATURE,
        system_prompt_path=llm.SYSTEM_PROMPT_PATH,
    )

    fake_chain.invoke.assert_called_once_with({"user_input": user_input})


def test_create_chain_success(monkeypatch):
    created_prompt_templates = []
    created_models = []

    class FakePromptTemplate:
        def __init__(self, messages, input_variables):
            self.messages = messages
            self.input_variables = input_variables
            created_prompt_templates.append(self)

        def __or__(self, model):
            return {
                "prompt_template": self,
                "model": model,
            }

    class FakeGeminiModel:
        def __init__(self, model, temperature):
            self.model = model
            self.temperature = temperature
            self.structured_schema = None
            self.structured_method = None
            created_models.append(self)

        def with_structured_output(self, schema, method):
            self.structured_schema = schema
            self.structured_method = method
            return self

    mock_load_system_prompt = MagicMock(return_value="SYSTEM PROMPT")

    monkeypatch.setattr(
        llm,
        "_load_system_prompt",
        mock_load_system_prompt,
    )

    monkeypatch.setattr(
        llm,
        "ChatPromptTemplate",
        FakePromptTemplate,
    )

    monkeypatch.setattr(
        llm,
        "ChatGoogleGenerativeAI",
        FakeGeminiModel,
    )

    chain = llm._create_chain(
        model_name="fake-model",
        temperature=0.5,
        system_prompt_path="/fake/system-prompt.md",
    )

    assert len(created_prompt_templates) == 1
    assert len(created_models) == 1

    prompt_template = created_prompt_templates[0]
    model = created_models[0]

    assert prompt_template.input_variables == ["user_input"]
    assert model.model == "fake-model"
    assert model.temperature == 0.5
    assert model.structured_schema == ProcessUserPromptOutput
    assert model.structured_method == "json_schema"

    assert chain["prompt_template"] == prompt_template
    assert chain["model"] == model

    mock_load_system_prompt.assert_called_once_with("/fake/system-prompt.md")
