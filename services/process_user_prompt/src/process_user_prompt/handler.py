"""Stub handler: returns hardcoded ``ProcessUserPromptResponse`` regardless of the input prompt.

Real implementation will call ``llm`` with a prompt-extraction system
message and parse the structured response..
"""

import logging

from dotenv import load_dotenv
from shared.schemas import ProcessUserPromptResponse, SearchRequest

from .llm import extract_data

load_dotenv()

logger = logging.getLogger("process_user_prompt.handler")


def handle(req: SearchRequest) -> ProcessUserPromptResponse:
    logger.info("User prompt extraction initilized!")
    data = extract_data(user_input=req.prompt)
    response_data = ProcessUserPromptResponse(prompt=req.prompt, request_id=req.request_id, **data.model_dump(mode="json"))
    logger.info("Data extracted from user prompt:", response_data.model_dump(mode="json"))
    logger.info("User prompt extraction finished")
    return response_data


if __name__ == "__main__":
    req = SearchRequest(
        request_id="req-1234",
        prompt="Me es indiferente si es piso o casa, con tal de que tenga jardín y sea en una zona con colegios cerca. Que cueste como mucho 30000 e imprescindible que tenga ascensor.",
    )
    handle(req)
