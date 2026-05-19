# Cloud deployment — status & punch list

Living doc. Updated as we go. Branch: `feature/cloud-infra`.

## Goal

All 4 worker services + frontend running on AWS (Lambda + managed
services), with a request flowing FE → API Gateway → SQS → Lambdas →
Qdrant Cloud → back to FE, plus an end-to-end trace lookup that
mirrors the local `tracer` UI.

## Current state

### ✅ Done

- **Branch shape**: `feature/cloud-infra` is develop's services + only
  the infra delta from `cloud_deployments`. 1 commit, 29 files.
- **Pulumi state backend**: `_bootstrap` stack — S3 + DDB lock, in
  account `466577275301`. Bucket name pinned per-account so
  teammates' deploys are deterministic.
- **Local-vs-cloud config switch**: `shared/sqs.py` already supports
  empty `SQS_ENDPOINT_URL` (skips passing endpoint+creds to boto3),
  resolves queue URLs via `GetQueueUrl`. No local behavior change.
- **`process_user_prompt` Lambda packaging**: `Dockerfile.lambda` +
  `lambda_handler.py` ready. Pulumi stack provisions Lambda + ESM.
- **`api-gateway` stack**: HTTP API + SQS service integration on
  `POST /search`, no Lambda hop.
- **`frontend` stack**: S3 + CloudFront, builds `npm run build` with
  `VITE_API_URL` from api-gateway endpoint.
- **`platform` stack (slim)**: 5 SQS queues + ECR + CW log group +
  SSM Gemini key — only `process_user_prompt` configured.
- **Makefile guards**: `make state-init`, `make login-remote`,
  `make up STACK=…` all preflight-check the inmo SSO session.

### ✅ Just landed this session

- **Qdrant Cloud signup**: cluster URL pinned in `platform/Pulumi.dev.yaml`,
  API key delivered out-of-band (sets via `make prompt-secrets`).
- **Platform expansion**: ECR + log groups for all 4 services, S3 HTML
  source bucket, DynamoDB user-data table, Qdrant URL/key SSM params.
- **`vector_query`**: `Dockerfile.lambda`, `lambda_handler.py`, full
  Pulumi stack with SSM-via-cold-start for both Gemini + Qdrant keys.
- **`ranking_and_rendering`**: same shape, only Qdrant key needed.
- **`data_ingestion`**: same shape + EventBridge cron rule + S3 read perms.
- **IAM tightening**: every service's `logs:*` is scoped to its own
  log group ARN (previously `Resource: "*"`); SSM perms scoped per-service
  (rr only gets Qdrant key, pup only Gemini, etc.).
- **`make deploy-all`**: one-shot deploy of all stacks in dependency
  order. Prompts (input hidden) for Gemini/Qdrant keys only if the
  SSM param is still the placeholder.

### How to deploy now

```bash
cd infra/pulumi

# One-time setup (per developer):
make install                            # uv sync of pulumi-aws + plugins
make state-init                         # if state bucket isn't created yet
make login-remote                       # switch CLI to S3 backend

# Full deploy of every stack in order:
make deploy-all                         # prompts for Gemini + Qdrant keys
                                        # if SSM still has placeholder values
```

After it finishes you'll see the CloudFront URL + API Gateway endpoint
printed. Submit a prompt from the FE and watch the trace via the
"Cloud monitoring" options below.

### ⏳ Not started

- **Response path for FE**: FE shows "siendo procesada" and stops.
  Needs `GET /results/{request_id}` endpoint on API Gateway (Lambda
  long-poll on `search-responses` for the matching message).
- **Cloud trace endpoint**: Replace local `tracer` with
  `GET /trace/{request_id}` — Lambda runs CloudWatch Logs Insights
  query across the 4 service log groups, returns the timeline. FE's
  "Ver traza →" link works again.
- **CI/CD**: GitHub Actions OIDC role + `pulumi-preview.yml` (PRs into
  main) + `pulumi-deploy.yml` (push to main). Gated on branch
  protection.
- **Cognito direct-poll** (phase 2): Replace the `GET /results/{id}`
  proxy with browser-side SQS polling using scoped IAM creds.

## Service-side blockers — none today

Verified `process_user_prompt.handler.handle()` returns
`ProcessUserPromptResponse`. Local end-to-end works (your `tracer`
proves it). No service-code blockers for the cloud deploy.

## Infra-required plumbing changes (additive, no local behavior change)

These live in `shared/` and `services/*/qdrant_client.py` because the
constructor takes the credential — but they're plumbing, not service
logic. Same carve-out we used for `shared/sqs.py`.

| File | Change |
|---|---|
| `shared/src/shared/settings.py` | Add `qdrant_api_key: str = ""` field |
| `services/vector_query/src/vector_query/qdrant_client.py` | `QdrantClient(url=…, api_key=settings.qdrant_api_key or None)` |
| `services/ranking_and_rendering/.../qdrant_client.py` | same |
| `services/data_ingestion/src/data_ingestion/handler.py` | same on the ad-hoc QdrantClient there |

Default `""` → `api_key=None` → no auth header → ElasticMQ-style local
behavior unchanged.

## Stacks (deploy order)

```
_bootstrap                       (one-time)
    ↓
platform                         (foundation for all services)
    ├── api-gateway              (POST /search ingress)
    │       └── frontend         (depends on api-gateway endpoint)
    ├── process-user-prompt      ✅ done
    ├── vector-query             🟡 building
    ├── ranking-and-rendering    🟡 building
    └── data-ingestion           🟡 building (also EventBridge)
```

## Open questions / decisions to make

- **Qdrant Cloud region**: pick `eu-west-1` to match the Lambda region
  if the free tier supports it; else closest. Latency ≠ correctness,
  cross-region is fine for a demo.
- **Response path style** (later): `GET /results/{id}` Lambda proxy
  (simpler) vs. Cognito direct-poll (faithful to original arch).
- **Tracing in cloud** (later): Lambda + Logs Insights wrapper vs.
  just use AWS console.

## Cloud monitoring

What you get out of the box (already wired by the Pulumi stacks; no
extra work):

| Source | What it gives you | Where |
|---|---|---|
| **CloudWatch Logs** | Every Lambda's stdout/stderr in a per-service log group | `/aws/lambda/inmo-dev-<service>` |
| **CloudWatch Metrics — Lambda** | Invocations, errors, duration, throttles, concurrent execs (auto-emitted, no instrumentation) | Console → Lambda → function → Monitor tab |
| **CloudWatch Metrics — SQS** | Messages sent/received/visible/in-flight/delayed, age of oldest message | Console → SQS → queue → Monitoring |
| **CloudWatch Metrics — API Gateway** | 4xx, 5xx, latency, count per route | Console → API Gateway → API → Monitor |
| **CloudWatch Logs Insights** | SQL-ish query language across log groups, ad-hoc | Console → CloudWatch → Logs Insights |

### Useful commands

```bash
# Tail one service's Lambda logs in your terminal:
make aws-logs                                       # default: process-user-prompt
make aws-logs SERVICE=vector-query                  # any service

# Cross-service trace by request_id (Logs Insights, in the console):
fields @timestamp, @logStream, @message
| filter @message like /<request_id>/
| sort @timestamp asc
```

Select all 4 service log groups when running the query — that's the
cloud equivalent of the local `tracer` UI.

### What we'd add later (not required for v1)

- **CloudWatch Alarms** — error-rate threshold per Lambda, DLQ depth,
  API Gateway 5xx spike. Free tier covers 10 alarms.
- **`GET /trace/{request_id}` Lambda** — wraps the Logs Insights
  query, returns JSON to the FE; "Ver traza →" link works again.
- **AWS X-Ray** — distributed tracing with auto-instrumentation. Adds
  cold-start latency. Free tier: 100K traces/month. Worth it once we
  start optimizing.
- **CloudWatch Dashboards** — pin the 6 most useful charts on one page
  for the demo.

## How to update this doc

When picking up an item:
1. Move it from "Not started" / "In progress" to the right column.
2. Add a one-line note about what was done or any gotcha discovered.
3. If a new question/decision shows up, append to "Open questions".
