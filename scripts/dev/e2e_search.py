"""End-to-end search simulator — what the frontend will eventually do.

Posts /search to api_gateway, captures the ``request_id``, then long-polls
``search-responses`` until a message with that ``request_id`` arrives. Prints
the response and exits.

Usage:
    uv run python scripts/dev/e2e_search.py [prompt words...]
"""

import json
import sys
from urllib.request import Request, urlopen

from shared.schemas import SearchResponse
from shared.settings import settings
from shared.sqs import consume


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "piso en Madrid 2 habitaciones"
    body = json.dumps({"prompt": prompt}).encode()
    req = Request(
        "http://localhost:8000/search",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        ack = json.loads(resp.read())
    print(f"posted: {ack}")
    print(f"waiting for response on {settings.queue_search_responses}...")

    for msg in consume(settings.queue_search_responses, SearchResponse):
        if msg.request_id == ack["request_id"]:
            print(msg.model_dump_json(indent=2))
            return


if __name__ == "__main__":
    main()
