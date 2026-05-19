# InmobiliarIA Júpiter — diagrams

Plain-ASCII diagrams (render in any terminal, editor, or PR view). For
service responsibilities and message contracts see
[`Architecture.md`](Architecture.md); for the cloud runtime decisions
see [`architecture2.md`](architecture2.md).

---

## 1. Service interactions (request flow + what each service does)

Logical view — what each service is responsible for and what messages
flow between them. Substrate-agnostic: identical shape for local
docker-compose and AWS Lambda.

```
                        ┌─────────┐
                        │  User   │
                        └────┬────┘
                             │  natural-language prompt
                             ▼
                    ┌────────────────┐
                    │    Frontend    │
                    └────────┬───────┘
                             │  POST /search  { prompt }
                             ▼
                    ┌────────────────┐
                    │  api_gateway   │
                    └────────┬───────┘
                             │  SearchRequest
                             ▼
              ┌──────────────────────────┐
              │   process_user_prompt    │   LLM extracts structured
              │      (Gemini call)       │   fields from the prompt
              └────────────┬─────────────┘
                           │  PromptFields  { fields, extra_info }
                           ▼
              ┌──────────────────────────┐         ┌──────────┐
              │     vector_query         │ ◄──────►│          │
              │  (embed prompt +         │  search │  Qdrant  │
              │   filtered top-K)        │  top-K  │          │
              └────────────┬─────────────┘         └─────▲────┘
                           │  RankJob  { doc_ids, filters }    │
                           ▼                                   │
              ┌──────────────────────────┐                     │
              │  ranking_and_rendering   │ ── fetch by id ─────┘
              │  (rerank with filters,   │
              │   build response)        │
              └────────────┬─────────────┘
                           │  SearchResponse  { ranked results }
                           ▼
                    ┌────────────────┐
                    │    Frontend    │ ────── renders ──────► User
                    └────────────────┘


  ─ ─ ─ async ingestion (cron-driven) ─ ─ ─

  ┌────────────┐       ┌──────────────────────┐       ┌──────────┐
  │ HTML files │ ────► │   data_ingestion     │ ────► │  Qdrant  │
  └────────────┘       │  parse → normalize → │       └──────────┘
                       │  embed → upsert      │
                       └──────────────────────┘
```

**Key**: solid `→` = synchronous call / publish on the live request
path. Dotted `─ ─ ─` = scheduled / out-of-band. Bidirectional `◄─►` =
request/response with Qdrant.

---

## 2. System map — LOCAL (docker-compose)

Every component runs as its own container; everything talks over the
`inmo` docker network.

```
  ┌──────────────────── docker-compose project: inmobiliaria ────────────────────┐
  │                                                                              │
  │  Browser ──► [frontend :5173] ──► [api_gateway :8000]                        │
  │                                          │                                   │
  │                                          ▼                                   │
  │                                   [ElasticMQ :9324] ◄──┐                     │
  │                                          │             │                     │
  │                          consume ───┐    │   ┌──── publish                   │
  │                                     ▼    ▼   │                               │
  │              ┌────────────────────────────────────┐                          │
  │              │  process_user_prompt   ──┐                                    │
  │              │  vector_query          ──┼─►  workers (one container each)    │
  │              │  ranking_and_rendering ──┘                                    │
  │              │  data_ingestion                                               │
  │              └─────────────┬──────────────────────┘                          │
  │                            │                                                  │
  │                            ▼                                                  │
  │                     [Qdrant :6333]                                            │
  │                                                                              │
  │  [api_gateway] ──► [DynamoDB Local :8001]   (user data, planned)             │
  │                                                                              │
  │  [tracer :9000] ─ ─ tails docker logs of every container, indexes by         │
  │                    request_id, exposes UI + JSON API                          │
  │                                                                              │
  └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. System map — CLOUD (AWS, Pulumi-managed)

No VPC, no Fargate, no ALB — everything is either a Lambda or a
managed service.

```
                              ┌─────────────┐
       Browser  ─────────────►│   S3        │
                              │ + CloudFront│ (static React build)
                              └──────┬──────┘
                                     │ POST /search
                                     ▼
                         ┌────────────────────────┐
                         │  API Gateway HTTP API  │  (SQS service integration,
                         └───────────┬────────────┘   no Lambda hop)
                                     │ SendMessage
                                     ▼
                  ┌────────────────────────────────────┐
                  │              SQS                   │  5 queues:
                  │  search-requests, query-jobs,      │   inmo-dev-queue-*
                  │  rank-jobs, search-responses,      │
                  │  ingest-jobs                       │
                  └─┬─────────────┬─────────────┬──────┘
                    │ event src   │             │
                    │ mapping     │             │
                    ▼             ▼             ▼
       ┌────────────────────────────────────────────────────┐
       │  Lambda (container image, one per service):        │
       │   process_user_prompt                              │
       │   vector_query  ───────────►  Qdrant Cloud         │
       │   ranking_and_rendering ───►  Qdrant Cloud         │
       │   data_ingestion ──────────►  Qdrant Cloud         │
       └─────────┬──────────────┬──────────────┬────────────┘
                 │              │              │
                 ▼              ▼              ▼
         ┌─────────────┐ ┌─────────────┐ ┌───────────────┐
         │     SSM     │ │ CloudWatch  │ │   DynamoDB    │
         │ GEMINI_API_ │ │   Logs      │ │ (user data)   │
         │ KEY         │ │             │ │               │
         └─────────────┘ └─────────────┘ └───────────────┘

         ┌────────────┐         ┌──────────────┐
         │EventBridge │ ──────► │ ingest-jobs  │ ─► data_ingestion Lambda
         │  schedule  │         │   (SQS)      │
         └────────────┘         └──────────────┘
                                      ▲
                                      │
                              ┌──────────────┐
                              │ S3 (HTML     │ (data_ingestion reads from here)
                              │  source)     │
                              └──────────────┘

         ┌──────────┐  pulled by every Lambda at cold start
         │   ECR    │  (one repo per service)
         └──────────┘
```

---

## 4. Search request — vertical pipeline

Time flows top to bottom. Each `→` is a real network hop.

```
  User
    │  types prompt + clicks "Buscar"
    ▼
  Frontend
    │  POST /search   { request_id, prompt }
    ▼
  API Gateway / api_gateway
    │  publish (SQS service integration / shared.sqs.publish)
    │
    ├─ returns 200 OK { request_id }
    │       │
    │       ▼
    │     Frontend → "Su petición está siendo procesada"
    ▼
  SQS: search-requests
    │  event source mapping (cloud)  /  long-poll (local)
    ▼
  process_user_prompt
    │  Gemini → structured fields
    │  publish
    ▼
  SQS: query-jobs
    ▼
  vector_query
    │  embed prompt (768-dim Gemini)
    │  build Qdrant filter
    │  similarity search ◄──► Qdrant
    │  publish
    ▼
  SQS: rank-jobs
    ▼
  ranking_and_rendering
    │  fetch full payloads ◄──► Qdrant
    │  rerank with filters
    │  publish
    ▼
  SQS: search-responses
    │
    │  (phase 2: FE long-polls this queue with Cognito-scoped IAM creds;
    │   today the response path is unwired — FE only shows
    │   "siendo procesada" and stops)
    ▼
  Frontend
```

---

## 5. Pulumi stack dependency graph

Same tier = independent (deploy in any order). Arrows go from
consumer stack to the stack it reads outputs from.

```
                       ┌──────────────┐
                       │  _bootstrap  │   S3 state bucket + DDB lock
                       │ LOCAL backend│   (one-time, chicken-and-egg)
                       └───────┬──────┘
                               │
                               ▼
                       ┌──────────────┐
                       │   platform   │   SQS · ECR · SSM ·
                       │              │   CloudWatch · DDB · S3
                       └─┬──┬──┬──┬──┘
              ┌──────────┘  │  │  │
              │             │  │  └──────────────────┐
              │             │  └────────┐            │
              ▼             ▼           ▼            ▼
        ┌──────────┐  ┌────────────┐  ┌──────────────────────┐
        │   api-   │  │  process-  │  │  vector-query,       │
        │ gateway  │  │   user-    │  │  ranking-and-        │
        │          │  │   prompt   │  │  rendering,          │
        └────┬─────┘  └────────────┘  │  data-ingestion      │
             │                         └──────────────────────┘
             ▼
        ┌──────────┐
        │ frontend │  reads api-gateway.endpoint (baked into VITE_API_URL)
        └──────────┘
```

---

## 6. Per-service code shape

Every Lambda-able service has the same layout. Local-dev `worker.py`
and cloud `lambda_handler.py` are siblings; both call the same
`handle()` function — no logic duplication.

```
  services/<svc>/
  ├── Dockerfile               (local docker-compose)
  ├── Dockerfile.lambda        (AWS Lambda container image)
  ├── pyproject.toml
  └── src/<svc>/
      ├── handler.py           ── pure logic (input → output)
      ├── worker.py            ── SQS long-poll loop  (local)
      ├── lambda_handler.py    ── SQS event-mapping wrapper (cloud)
      └── *.py                 ── service-specific modules
                                  (llm.py, embeddings.py,
                                   filters.py, ranker.py, …)

  ┌────────────────┐               ┌────────────────────┐
  │   worker.py    │ ── handle() ──┤                    │
  │   (local)      │               │   handler.py       │
  └────────────────┘               │  (shared logic)    │
                                   │                    │
  ┌────────────────┐ ── handle() ──┤                    │
  │ lambda_handler │               │                    │
  │   (cloud)      │               └────────────────────┘
  └────────────────┘
```

---

## 7. Message contracts

| Queue              | Producer                | Consumer               | Schema                          |
|--------------------|-------------------------|------------------------|---------------------------------|
| `search-requests`  | api_gateway / API GW    | process_user_prompt    | `SearchRequest`                 |
| `query-jobs`       | process_user_prompt     | vector_query           | `ProcessUserPromptResponse`     |
| `rank-jobs`        | vector_query            | ranking_and_rendering  | `RankJob`                       |
| `search-responses` | ranking_and_rendering   | frontend (phase 2)     | `SearchResponse`                |
| `ingest-jobs`      | EventBridge / cron      | data_ingestion         | `IngestJob`                     |

Schemas live in [`shared/src/shared/schemas.py`](../shared/src/shared/schemas.py).
Every message carries a `request_id` so the chain can be correlated
end-to-end (locally via the `tracer` service, in cloud via CloudWatch
Logs Insights).
