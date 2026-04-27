from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

SYSTEM_PROMPT_FILE_PATH = "./generate-summary-prompt.md"
LLM_MODEL_NAME = "gemini-3.1-flash-lite-preview"


def _get_system_prompt() -> str:
    with open(SYSTEM_PROMPT_FILE_PATH) as f:
        system_prompt = f.read()
    return system_prompt


_prompt_template = ChatPromptTemplate(
    [
        SystemMessage(_get_system_prompt()),
        ("user", "{text}"),
    ],
    input_variables=["text"],
)

_model = ChatGoogleGenerativeAI(model=LLM_MODEL_NAME, temperature=1)
_chain = _prompt_template | _model | StrOutputParser()


def normalize_descriptions(descriptions: list[str]) -> list[str]:
    return _chain.batch([{"text": desc} for desc in descriptions], config={"max_concurrency": 1})
