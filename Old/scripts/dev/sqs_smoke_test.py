"""Smoke test: publish a dummy SearchRequest to ``search-requests`` and read it back.

Run after ``make up`` to verify ElasticMQ and the ``shared.sqs`` wrapper work
together on the host. Exits 0 on success, non-zero on assertion failure.
"""

import uuid

from shared.schemas import SearchRequest
from shared.settings import settings
from shared.sqs import consume, publish


def main() -> None:
    req = SearchRequest(request_id=str(uuid.uuid4()), prompt="piso en Madrid 2 habitaciones")
    publish(settings.queue_search_requests, req)
    print(f"published {req.request_id}")

    for msg in consume(settings.queue_search_requests, SearchRequest):
        print(f"received {msg.request_id}")
        assert msg.request_id == req.request_id
        break

    print("ok")


if __name__ == "__main__":
    main()
