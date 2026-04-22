"""Consume and print one message from the ``search-requests`` queue.

Destructive: the message is deleted after printing. Used while no worker is
consuming ``search-requests`` yet, to confirm api_gateway actually publishes.
"""

from shared.schemas import SearchRequest
from shared.settings import settings
from shared.sqs import consume


def main() -> None:
    for msg in consume(settings.queue_search_requests, SearchRequest):
        print(msg.model_dump_json(indent=2))
        break


if __name__ == "__main__":
    main()
