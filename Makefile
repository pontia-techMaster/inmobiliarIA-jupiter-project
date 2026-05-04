.PHONY: up down logs ps smoke sync post-search peek-search-requests api-dev e2e trigger-ingestion bootstrap

sync:
	uv sync --all-packages

up:
	docker compose -f infra/docker-compose.yml up -d --build

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

ps:
	docker compose -f infra/docker-compose.yml ps

smoke:
	uv run python scripts/dev/sqs_smoke_test.py

post-search:
	curl -s -X POST http://localhost:8000/search \
		-H 'Content-Type: application/json' \
		-d '{"prompt": "piso en Madrid 2 habitaciones"}' && echo

peek-search-requests:
	uv run python scripts/dev/peek_search_requests.py

api-dev:
	uv run --package api_gateway uvicorn api_gateway.main:app --port 8000 --reload

e2e:
	uv run python scripts/dev/e2e_search.py

trigger-ingestion:
	uv run python scripts/dev/trigger_ingestion.py

bootstrap:
	uv run python scripts/dev/bootstrap_qdrant.py
