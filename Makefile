.PHONY: up down logs ps smoke sync post-search peek-search-requests api-dev e2e trigger-ingestion bootstrap fe-dev fe-build sqs-list sqs-peek sqs-purge sqs-send sqs-attrs

sync:
	uv sync --all-packages --all-groups 

up:
	docker compose --env-file .env -f infra/docker-compose.yml up -d --build

down:
	docker compose --env-file .env -f infra/docker-compose.yml down

logs:
	docker compose --env-file .env -f infra/docker-compose.yml logs -f

ps:
	docker compose --env-file .env -f infra/docker-compose.yml ps

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

fe-dev:
	cd services/frontend && npm install && npm run dev

fe-build:
	cd services/frontend && npm install && npm run build

# ─── SQS dev helpers ──────────────────────────────────────────────────────────
# Run the AWS CLI from a throwaway container on the compose network. No host
# install needed; talks to ElasticMQ over the inmo network. Requires `make up`.
SQS_DOCKER = docker run --rm --network inmobiliaria_inmo \
	-e AWS_ACCESS_KEY_ID=x -e AWS_SECRET_ACCESS_KEY=x -e AWS_REGION=elasticmq \
	amazon/aws-cli --endpoint-url http://elasticmq:9324
SQS_QURL = http://elasticmq:9324/000000000000

sqs-list:
	$(SQS_DOCKER) sqs list-queues

sqs-peek:
	@test -n "$(QUEUE)" || (echo "usage: make sqs-peek QUEUE=<name>"; exit 1)
	$(SQS_DOCKER) sqs receive-message \
		--queue-url $(SQS_QURL)/$(QUEUE) \
		--visibility-timeout 0 \
		--wait-time-seconds 1 \
		--max-number-of-messages 1

sqs-purge:
	@test -n "$(QUEUE)" || (echo "usage: make sqs-purge QUEUE=<name>"; exit 1)
	$(SQS_DOCKER) sqs purge-queue --queue-url $(SQS_QURL)/$(QUEUE)

sqs-send:
	@test -n "$(QUEUE)" || (echo "usage: make sqs-send QUEUE=<name> BODY='<json>'"; exit 1)
	@test -n "$(BODY)" || (echo "usage: make sqs-send QUEUE=<name> BODY='<json>'"; exit 1)
	$(SQS_DOCKER) sqs send-message --queue-url $(SQS_QURL)/$(QUEUE) --message-body '$(BODY)'

sqs-attrs:
	@test -n "$(QUEUE)" || (echo "usage: make sqs-attrs QUEUE=<name>"; exit 1)
	$(SQS_DOCKER) sqs get-queue-attributes \
		--queue-url $(SQS_QURL)/$(QUEUE) \
		--attribute-names All
