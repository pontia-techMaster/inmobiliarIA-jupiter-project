import logging
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from shared.schemas import ProcessUserPromptOutput

logger = logging.getLogger("process_user_prompt.llm")

SYSTEM_PROMPT_PATH = str(Path(__file__).parent / "system-prompt.md")
GEMINI_MODEL_NAME = "gemini-3.1-flash-lite-preview"
MODEL_TEMPERATURE = 0.2


def _load_system_prompt(file_path: str) -> str:
    return Path(file_path).read_text()


def _create_chain(model_name: str, temperature: float, system_prompt_path: str):

    prompt_template = ChatPromptTemplate(
        [
            SystemMessage(_load_system_prompt(system_prompt_path)),
            ("user", "{user_input}"),
        ],
        input_variables=["user_input"],
    )

    model = ChatGoogleGenerativeAI(model=model_name, temperature=temperature).with_structured_output(
        schema=ProcessUserPromptOutput, method="json_schema"
    )
    chain = prompt_template | model

    return chain


def extract_data(user_input: str) -> ProcessUserPromptOutput:
    chain = _create_chain(model_name=GEMINI_MODEL_NAME, temperature=MODEL_TEMPERATURE, system_prompt_path=SYSTEM_PROMPT_PATH)
    return chain.invoke({"user_input": user_input})
