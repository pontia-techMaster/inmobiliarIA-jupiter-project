# vector_query — implementation notes & ingestion contract

This document explains what the `vector_query` service does after the
implementation we just landed, and lists what needs to be agreed with whoever
is building `data_ingestion` so the two halves of the pipeline work together.

---

## What it does

`vector_query` consumes structured search jobs from SQS `query-jobs`, runs a
filtered semantic search against Qdrant, and publishes the top-K candidate
document IDs to SQS `rank-jobs`.

```
PromptFields  (from process_user_prompt)
     ↓ embed prompt → 768-dim vector
     ↓ build Qdrant filter from structured fields
     ↓ similarity search (top-K)
RankJob  (to ranking_and_rendering)
```

It does **not**:

- speak HTTP — it is a worker, not an endpoint
- rank, score, or render results — that's `ranking_and_rendering`
- write to Qdrant — that's `data_ingestion`
- talk to the LLM — that's `process_user_prompt`

---

## The pipeline, step by step

For one input message:

```python
job = PromptFields(
    request_id="<uuid>",
    prompt="ático luminoso con vistas en barrio elegante",
    fields={"district": "Barrio de Salamanca", "min_rooms": 2, "max_price": 1_500_000},
)
```

1. **Embed the prompt.** `embed_query(job.prompt)` returns a 768-dim vector.
   Calls real Gemini if `GEMINI_API_KEY` is set, falls back to a deterministic
   hash-based stub if not.
2. **Build the filter.** `filters.build(job.fields)` returns a Qdrant `Filter`
   (or `None` if no recognised fields are present).
3. **Search.** `qdrant_client.search(vector, filter, k=20)` runs `query_points`
   on the `properties` collection and returns `[(idealista_id, score), ...]`
   sorted by descending similarity.
4. **Publish.** Pack the IDs into `RankJob` and publish to `rank-jobs`.

---

## The four files inside the service

```
services/vector_query/src/vector_query/
├── handler.py          # ~30 lines: the orchestrator (steps 1–4 above)
├── embeddings.py       # thin re-export of embeddings.embed_query
├── filters.py          # PromptFields.fields → qdrant.Filter
├── qdrant_client.py    # similarity-search wrapper
└── worker.py           # SQS long-poll loop (calls handler.handle)
```

`worker.py` is the local-dev entrypoint. For Lambda we add a sibling
`lambda_handler.py` later (Phase 2 — see end of doc). Both call
`handler.handle()`; the actual logic stays in one place.

---

## Why `embeddings/` is its own workspace package

It lives at the repo root, next to `shared/` and `services/`:

```
embeddings/
└── src/embeddings/
    ├── config.py    # MODEL, DIMENSIONS, task type constants
    └── gemini.py    # embed_query(), embed_documents()
```

Two services need to embed: **`vector_query`** (queries, `RETRIEVAL_QUERY`
task type) and **`data_ingestion`** (documents, `RETRIEVAL_DOCUMENT` task type).
Their vectors must be in the **same space** — same model, same dimension —
otherwise similarity search returns garbage.

Putting the wrapper in its own package means:

- One source of truth for model + dimension constants (`config.py`).
- Both services depend on it explicitly via the workspace.
- `api_gateway`, `process_user_prompt`, `ranking_and_rendering` do **not**
  pull the heavy `langchain-google-genai` SDK into their images.

---

## Stub vs real embeddings

`embeddings/gemini.py` checks for `GEMINI_API_KEY` (or `GOOGLE_API_KEY`):

- **Set** → real Gemini API call.
- **Unset** → deterministic hash-based stub vector. Plumbing works, but
  similarity scores are meaningless.

Stub mode is for testing the pipeline without spending API credits. Real
search needs the real key. Both ingestion and vector_query honour the same
env var via the shared package.

To run with real embeddings:

```bash
export GEMINI_API_KEY=...
make up
make bootstrap   # the existing Old/data was already embedded with Gemini,
                 # so the vectors in Qdrant are real either way
make e2e
```

---

## How to test locally

```bash
make up          # infra + all 5 services
make bootstrap   # one-shot: load 49 properties + pre-computed vectors into Qdrant
make e2e         # POST /search → wait on search-responses → print
```

Expected: a `SearchResponse` with `results` whose `id`s are real
`idealista_id`s like `103883825`.

To watch a single request flow through the chain:

```bash
docker logs vector_query --tail 20
```

Each service logs `request_id=...` and the payloads at consume / publish, so
you can grep one search across all containers.

---

## What needs agreement with your teammate (ingestion contract)

The data your teammate's `data_ingestion` writes to Qdrant is what
`vector_query` reads. **Get these wrong and the chain breaks silently** —
zero hits, garbage hits, or runtime errors when filtering.

### 1. Embedding function — use the shared package

✅ **Must call `embeddings.embed_documents(texts)`** from the workspace
package — not a custom Gemini call, not a different model.

```python
from embeddings import embed_documents

vectors = embed_documents([text_for_property(p) for p in properties])
```

Guarantees same model (`gemini-embedding-001`), same dimension (768), correct
task type (`RETRIEVAL_DOCUMENT`). vector_query uses `embed_query` from the
same package with `RETRIEVAL_QUERY`. The two task types are compatible.

If they roll their own client, set a different model, or use a different task
type, similarity search returns random-looking results.

### 2. What text gets embedded

Open question. Three reasonable choices:

- **Raw `description`** from the listing — verbose, includes noise
- **Normalized `summary`** — LLM-cleaned one-liner (this is what
  `Old/data/embeddings.json` was generated from)
- **A structured concatenation** — e.g. `"{property_type} en {district},
  {rooms} habitaciones. {description}"`

The existing data in `Old/data/embeddings.json` used the normalized summary.
Recommendation: keep it that way unless you both want to redo it. Summaries
are short, clean, and capture the gist.

### 3. Collection name

✅ **Must be `settings.qdrant_collection`** (default `"properties"`). Both
services read from `shared.settings`. Don't hardcode a different name in
ingestion.

### 4. Collection params (vector size, distance)

If `data_ingestion` creates the collection itself:

- `size = embeddings.config.DIMENSIONS` (= 768)
- `distance = COSINE`

These match the bootstrap script. If the collection already exists with
different params, re-creating silently is bad — best is to check existence
and create only if missing.

### 5. Point ID convention

✅ **Use the integer `idealista_id` as the Qdrant point ID.** That's what
`bootstrap_qdrant.py` does. vector_query returns these IDs verbatim in
`RankJob`, so `ranking_and_rendering` (and ultimately the FE) needs to look
up properties by `idealista_id`.

### 6. Payload schema

Every point's payload **must** contain at least these keys, exactly as
named — vector_query filters on them:

| key                | type      | required | how vector_query uses it |
|--------------------|-----------|----------|--------------------------|
| `idealista_id`     | int       | yes      | returned to client       |
| `district`         | str       | yes      | exact-match filter       |
| `neighborhood`     | str       | no       | exact-match filter       |
| `property_type`    | str       | no       | exact-match filter       |
| `property_subtype` | str       | no       | exact-match filter       |
| `price`            | int (EUR) | no       | range filter (gte/lte)   |
| `rooms`            | int       | no       | range filter (gte/lte)   |
| `surface`          | int (m²)  | no       | range filter (gte/lte)   |
| `bathrooms`        | int       | no       | (display only)           |
| `street`           | str       | no       | (display only)           |
| `summary`          | str       | no       | (display only)           |

Field names are **case-sensitive**. Writing `District`, `numRooms`, or
`pricing` won't match.

To add a new filterable field later (e.g. `has_parking`), you have to update
both `data_ingestion` (write it to payload) and
`vector_query.filters._EXACT` / `_RANGES` (register it as filterable).

### 7. Idempotency

`data_ingestion` should use Qdrant's **upsert**, not insert, so re-running
on the same data updates the point instead of duplicating it. The bootstrap
script already does this.

### 8. Where the source data comes from

Open question — the realistic vs the pragmatic path:

- **(a) Full pipeline**: read raw HTML from `Old/data/source_html/`, parse
  with BeautifulSoup, normalize descriptions via Gemini, embed via Gemini,
  upsert. Realistic but each Gemini regeneration costs a few cents.
- **(b) Skip the work**: read `Old/data/parsed-properties.json` +
  `embeddings.json`, upsert directly (same as `bootstrap_qdrant.py`).
  Cheap and fast, but doesn't exercise the actual ingestion pipeline.

For the **May 20 demo**: (b) is probably enough — what we want to
demonstrate is the microservice topology, not the regeneration. The
`data_ingestion` worker can read the JSONs and treat them as if it had
parsed them. (a) is post-demo work.

### 9. `IngestJob` payload — what triggers a run

Currently the schema is `IngestJob(source: str)`. Possible conventions:

- `"all"` → re-ingest everything from the predetermined source
- `"/data/html"` → parse all HTML files in this directory
- a single file path → re-ingest just one property

Recommend `"all"` for now — keeps the worker simple. Decide once your
teammate starts writing the loop.

### 10. Who creates the Qdrant collection

Two reasonable options:

- **Bootstrap script (current)** — a dev runs `make bootstrap` once, the
  collection exists, `data_ingestion` only upserts.
- **`data_ingestion` checks-and-creates on each run** — cleaner, no separate
  step. If you go this way, factor the "create if missing" code into the
  shared `embeddings` package (or a new shared module) so the params can't
  drift between services.

Either is fine. The first is simpler; the second is more self-contained.

---

## Known issues / things to fix later

1. **Filter contract drift.** `process_user_prompt` currently emits
   `{"rooms": 2}` (canned stub), but `vector_query` recognises
   `min_rooms`/`max_rooms` (ranges), not exact `rooms`. The filter just
   logs `ignoring unknown filter keys: ['rooms']` and returns top-K of
   everything matching the rest. To be fixed when the real LLM extractor
   in `process_user_prompt` is implemented and emits the agreed schema.

2. **Qdrant client/server version skew.** Client `1.17.1` (installed by
   `qdrant-client>=1.12,<2`) vs server `1.12.4` (the
   `qdrant/qdrant:v1.12.4` image we pin). Warning at runtime, no
   functional impact. Fix by bumping the image tag to `v1.17.x` in
   `infra/docker-compose.yml`.

3. **Stub embedding scores are meaningless.** By design — but the demo
   needs `GEMINI_API_KEY` set to be convincing.

4. **`QueryJob` schema is unused.** `shared/schemas.py` defines
   `QueryJob` but the chain actually uses `PromptFields` on `query-jobs`.
   Dead code; safe to remove later.

---

## Phase 2 — Lambda packaging (not done yet)

When you're ready, two files plus a Pulumi micro-stack:

```python
# services/vector_query/src/vector_query/lambda_handler.py
def handler(event, context):
    for record in event["Records"]:
        job = PromptFields.model_validate_json(record["body"])
        out = handle(job)                         # same handler.handle as today
        publish(settings.queue_rank_jobs, out)
```

```dockerfile
# services/vector_query/Dockerfile.lambda
FROM public.ecr.aws/lambda/python:3.12
# (same uv-based install pattern as the existing Dockerfile)
CMD ["vector_query.lambda_handler.handler"]
```

Plus a Pulumi stack defining: the Lambda function (container image), IAM
role with SQS read on `query-jobs` and SQS write on `rank-jobs`, an SQS
event source mapping, and reading `GEMINI_API_KEY` from SSM Parameter
Store at cold start.

`handler.py`, `filters.py`, `qdrant_client.py`, `embeddings.py` stay
unchanged from local-dev.
