# vector_query

SQS worker that turns a structured search job into a list of candidate
property IDs by running a filtered semantic search against Qdrant.

```
PromptFields  (SQS: query-jobs)
     ↓ embed prompt → 768-dim vector
     ↓ build Qdrant filter from structured fields
     ↓ similarity search (top-K)
RankJob  (SQS: rank-jobs)
```

## Inputs / outputs

**Consumes** `query-jobs`:

```python
PromptFields(
    request_id: str,
    prompt: str,                   # original natural-language query
    fields: dict[str, Any],        # structured filters from process_user_prompt
)
```

**Publishes** `rank-jobs`:

```python
RankJob(
    request_id: str,
    doc_ids: list[str],            # idealista_ids, sorted by similarity desc
    filters: dict[str, Any],       # echo of the input filters
)
```

## Files

```
src/vector_query/
├── handler.py          # orchestrator: embed → filter → search → pack
├── embeddings.py       # re-exports embed_query from the shared `embeddings/` package
├── filters.py          # PromptFields.fields → qdrant.Filter
├── qdrant_store.py    # similarity-search wrapper
└── worker.py           # SQS long-poll loop (calls handler.handle)
```

`worker.py` is the local-dev entrypoint. Lambda packaging will add a sibling
`lambda_handler.py` — see [docs/VECTOR_QUERY.md](../../docs/VECTOR_QUERY.md#phase-2--lambda-packaging-not-done-yet).

## Filterable fields

`filters.build()` recognises:

| Key                                         | Type   | Filter           |
|---------------------------------------------|--------|------------------|
| `district`, `neighborhood`,                 | str    | exact match      |
| `property_type`, `property_subtype`         |        |                  |
| `min_price` / `max_price` → `price`         | int    | range (gte/lte)  |
| `min_rooms` / `max_rooms` → `rooms`         | int    | range            |
| `min_surface` / `max_surface` → `surface`   | int    | range            |

Unknown keys are logged and ignored. Values must match the payload schema
that `data_ingestion` writes to Qdrant — see
[docs/VECTOR_QUERY.md](../../docs/VECTOR_QUERY.md#what-needs-agreement-with-your-teammate-ingestion-contract)
for the contract.

## Configuration (env vars)

| Variable             | Default                  | Notes                                                     |
|----------------------|--------------------------|-----------------------------------------------------------|
| `SQS_ENDPOINT_URL`   | `http://localhost:9324`  | ElasticMQ locally, real SQS in cloud                      |
| `QDRANT_URL`         | `http://localhost:6333`  | Local container or Qdrant Cloud                           |
| `QDRANT_COLLECTION`  | `properties`             | Must match `data_ingestion`                               |
| `TOP_K`              | `20`                     | Candidates returned for ranking                           |
| `GEMINI_API_KEY`     | (unset)                  | Real Gemini if set, deterministic stub vector if not      |

## Run locally

From repo root:

```bash
make up          # infra + all services (vector_query included)
make bootstrap   # seed Qdrant with 49 properties from Old/data
make e2e         # POST /search and read the response — exercises the chain
```

Trace one container:

```bash
docker logs vector_query --tail 20
```

## Dependencies

- [`shared`](../../shared) — message schemas, settings, SQS wrapper
- [`embeddings`](../../embeddings) — Gemini wrapper (`embed_query`) with stub fallback
- `qdrant-client` — Qdrant Python SDK

## Further reading

- [`docs/VECTOR_QUERY.md`](../../docs/VECTOR_QUERY.md) — implementation notes,
  contract with `data_ingestion`, known issues, Lambda packaging preview
- [`docs/Architecture.md`](../../docs/Architecture.md) — overall system design
- [`docs/DESARROLLO.md`](../../docs/DESARROLLO.md) — guía de desarrollo local
