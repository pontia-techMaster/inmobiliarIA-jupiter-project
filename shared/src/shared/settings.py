"""Environment-based configuration shared by all services.

Values come from env vars (and a local ``.env`` when running on the host).
Defaults target host-side usage (``localhost``); inside docker-compose each
container gets its endpoints overridden via ``environment:`` to point at the
compose network hostnames (``elasticmq``, ``qdrant``, ``dynamodb``).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sqs_endpoint_url: str = "http://localhost:9324"
    aws_region: str = "elasticmq"
    aws_access_key_id: str = "x"
    aws_secret_access_key: str = "x"

    queue_search_requests: str = "search-requests"
    queue_query_jobs: str = "query-jobs"
    queue_rank_jobs: str = "rank-jobs"
    queue_search_responses: str = "search-responses"
    queue_ingest_jobs: str = "ingest-jobs"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""  # empty → no auth header (local Qdrant container)
    qdrant_collection_name: str = "properties"
    qdrant_top_k: int = 10
    dynamodb_endpoint_url: str = "http://localhost:8001"


settings = Settings()
