"""Stub handler: returns hardcoded ``PromptFields`` regardless of the input prompt.

Real implementation will call ``llm_client`` with a prompt-extraction system
message and parse the structured response. For now this returns a canned
``{"city": "Madrid", "rooms": 2}`` so we can verify end-to-end plumbing.
"""

import logging

from shared.schemas import PromptFields, SearchRequest

log = logging.getLogger("process_user_prompt.handler")


def handle(req: SearchRequest) -> PromptFields:
    log.info("stub handler: request_id=%s prompt=%r → canned fields", req.request_id, req.prompt)
    return PromptFields(
        request_id=req.request_id,
        fields={"city": "Madrid", "rooms": 2},
    )
