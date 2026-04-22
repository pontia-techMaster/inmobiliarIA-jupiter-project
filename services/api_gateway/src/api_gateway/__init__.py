"""api_gateway: FastAPI entrypoint exposing /search and /users to the frontend.

Replaced by API Gateway in cloud. The HTTP routes themselves carry no business
logic — ``POST /search`` publishes a SearchRequest onto the ``search-requests``
SQS queue and returns its ``request_id`` to the caller, which will later
consume the matching response from ``search-responses``.
"""
