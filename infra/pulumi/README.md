# Pulumi microstacks — InmobiliarIA Júpiter

Cloud infrastructure for the project, organised as small composable
stacks. See [`docs/architecture2.md`](../../docs/architecture2.md) for
the cloud topology this provisions and
[`docs/deployment-status.md`](../../docs/deployment-status.md) for the
living deploy tracker.

## Layout

```
.
├── pyproject.toml             shared deps for every stack (one venv)
├── uv.lock
├── Makefile                   one-shot deploy + per-stack wrappers
├── _shared/                   python helpers: naming, tags, stack refs
├── _bootstrap/                S3 state bucket + DDB lock (LOCAL backend)
├── platform/                  SQS, ECR, SSM, CloudWatch, S3 source, DynamoDB
├── api-gateway/               HTTP API + SQS service integration
├── frontend/                  S3 + CloudFront
├── process-user-prompt/       Lambda + SQS event source mapping
├── vector-query/              Lambda + ESM (Qdrant query)
├── ranking-and-rendering/     Lambda + ESM (Qdrant fetch + rerank)
└── data-ingestion/            Lambda + ESM + EventBridge cron
```

Eight deployable stacks. `_bootstrap` and `_shared` are special:
`_bootstrap` uses the LOCAL Pulumi backend (chicken-and-egg — it
creates the S3 bucket every other stack uses); `_shared` is a regular
Python package used by all other stacks via `import _shared`.

## Prerequisites

- **AWS CLI** with an SSO profile named **`inmo`** pointing at the
  deploy account. Every `Pulumi.dev.yaml` pins `aws:profile: inmo`,
  and the Makefile also `export`s `AWS_PROFILE=inmo` so the AWS Go SDK
  resolves the right credentials. SSO sessions last ~8h; refresh with
  `aws sso login --profile inmo` when expired.

  First-time setup:
  ```bash
  aws configure sso --profile inmo
  # session name:        pontia
  # SSO start URL:       https://pontia.awsapps.com/start    (no #fragment)
  # SSO region:          eu-west-1
  # registration scopes: (leave blank → default sso:account:access)
  # browser opens, approve, pick account + AdministratorAccess role
  # CLI region:          eu-west-1
  # output format:       json
  # profile name:        inmo
  aws --profile inmo sts get-caller-identity   # confirm right account
  ```

- **Pulumi CLI**: `brew install pulumi/tap/pulumi`.
- **Docker daemon** running — service stacks build Lambda container
  images via `pulumi-docker-build`.
- **Node 20+** — the `frontend` stack runs `npm install && npm run build`.

The `check-sso` Make target acts as a preflight on every cloud-touching
command, so an expired SSO session fails fast with a friendly message
rather than silently falling back to other creds.

## One-time setup (per developer)

```bash
cd infra/pulumi

# 1. Create venv with Pulumi + plugins
make install

# 2. Initialize remote state — uses LOCAL backend (chicken-and-egg)
#    Creates `inmo-dev-pulumi-state-<account-id>` (S3) + DDB lock table.
make state-init

# 3. Switch the Pulumi CLI to the S3 backend.
#    Auto-discovers the bucket name from the inmo profile's account id;
#    no env var to set by hand.
make login-remote
```

Subsequent teammates skip step 2 (state bucket already exists in the
account) — just `make install` + `make login-remote`.

## Full deploy (recommended)

One target deploys everything in dependency order, prompting for any
SSM SecureString that's still a placeholder:

```bash
make deploy-all
```

Sequence:

1. `platform` — creates SQS queues, ECR repos, SSM placeholders, log
   groups, S3 HTML source bucket, DynamoDB users table.
2. **Prompts** (input hidden) for `inmo-dev-gemini-api-key` and
   `inmo-dev-qdrant-api-key`. Skips any that's already set to a non-
   placeholder value. Set them later with `make prompt-secrets`.
3. `api-gateway`, then the 4 service Lambdas (`process-user-prompt`,
   `vector-query`, `ranking-and-rendering`, `data-ingestion`), then
   `frontend`. Each builds + pushes its container image to ECR.
4. Prints the CloudFront URL + API Gateway endpoint at the end.

Re-runnable: Pulumi diffs each stack and no-ops on unchanged
resources. If a stack fails the run aborts with a hint to fix and
re-run.

### Per-stack deploy (when iterating on one service)

```bash
make up STACK=vector-query        # pulumi up on one stack
make preview STACK=vector-query   # pulumi preview (no changes applied)
make outputs STACK=api-gateway    # JSON of stack outputs
make destroy STACK=frontend       # destroy a single stack
```

## Stacks (deploy graph)

```
_bootstrap                                   (S3 state bucket + DDB lock)
    │
platform                                     (SQS · ECR · SSM · CloudWatch ·
    │                                         S3 source · DDB users)
    ├── api-gateway                          (HTTP API → SQS:search-requests)
    │       │
    │       └── frontend                     (S3 + CloudFront, reads api endpoint)
    │
    ├── process-user-prompt                  (SQS:search-requests → query-jobs)
    ├── vector-query                         (SQS:query-jobs → rank-jobs + Qdrant)
    ├── ranking-and-rendering                (SQS:rank-jobs → search-responses + Qdrant)
    └── data-ingestion                       (SQS:ingest-jobs + EventBridge cron + S3)
```

## Day-2 ops

| Target | What it does |
|---|---|
| `make deploy-all` | Full deploy in order (idempotent) |
| `make destroy-all` | Reverse-order destroy of every stack except `_bootstrap`. Type `destroy` to confirm |
| `make prompt-secrets` | Re-prompt for Gemini / Qdrant keys (only if still `REPLACE_ME`) |
| `make show-cloud-resources` | Print live FE/API URLs + console deep-links for every service |
| `make aws-logs` (or `SERVICE=<name>`) | Live-tail one Lambda's CloudWatch log group (default `process-user-prompt`) |
| `make fe-invalidate` | Flush CloudFront cache for the frontend distribution after `make up STACK=frontend` |
| `make seed-html` | Sync `services/data_ingestion/data/source_html/` → S3 ingestion bucket |
| `make trigger-ingestion` | Publish an `IngestJob` to `ingest-jobs` so the Lambda processes the S3 prefix on demand (otherwise it runs on the EventBridge cron, Mondays 03:00 UTC) |
| `make check-sso` | Verify the `inmo` SSO session is alive. All cloud targets depend on this |

## Adding a new service stack

1. Copy `process-user-prompt/` to `<service>/`.
2. Edit `Pulumi.yaml` (project name, description).
3. Edit `__main__.py`:
   - Change `SERVICE` constant at the top.
   - Change the input queue (e.g. `platform.queue_arn("query-jobs")`)
     and output queue to whatever this service consumes/produces.
   - Update the IAM policy to scope SQS perms to those queues.
4. Add a `Dockerfile.lambda` next to the service code (template:
   `services/process_user_prompt/Dockerfile.lambda`). Key bits:
   - `FROM public.ecr.aws/lambda/python:3.12`
   - Install deps into `${LAMBDA_TASK_ROOT}` via uv export → pip
   - **End with `WORKDIR ${LAMBDA_TASK_ROOT}`** — otherwise Lambda
     errors out with `Runtime.InvalidWorkingDir`.
5. Add `lambda_handler.py` next to `worker.py` in the service src.
   At cold-start it should fetch any needed secrets from SSM and set
   them as env vars before importing `handler.py`.
6. **Set the cloud env vars on the Lambda** — see
   [`docs/architecture2.md` § Service runtime config](../../docs/architecture2.md#service-runtime-config--local-vs-cloud)
   for the full table. At minimum:
   - `SQS_ENDPOINT_URL=""` so `shared/sqs.py` uses real SQS.
   - `QUEUE_<OUTPUT>=<actual-cloud-queue-name>` for every queue the
     service writes to.
7. Add the service to `platform/Pulumi.dev.yaml` `services:` list and
   re-run `make up STACK=platform` so the ECR repo + log group exist.
8. `make up STACK=<service>` — or just `make deploy-all`.

## Quirks worth knowing

- **`AWS_PROFILE=inmo` is exported by the Makefile.** With SSO, the
  Go SDK can silently fall back to your default profile if `inmo`
  isn't found in env. The Make-level export prevents that.
- **`pulumi-docker-build` (0.0.15) doesn't expose `provenance`/`sbom`
  as direct kwargs.** We pass them via `exports=[ExportArgs(raw=…)]`
  to disable both — Lambda only accepts plain image manifests, not
  the OCI image-index format buildx defaults to. Each service's
  `__main__.py` includes the workaround.
- **Lambda `image_uri` must be `<repo>@<digest>` OR `<repo>:<tag>`,
  not the combined `<repo>:<tag>@<digest>` that `image.ref` returns.**
  All service stacks build the digest-pinned form manually.
- **ECR repos need a `RepositoryPolicy`** allowing
  `lambda.amazonaws.com` to `BatchGetImage` + `GetDownloadUrlForLayer`
  in the same account. Without it, `CreateFunction` fails with the
  cryptic "Source image is not valid". `platform/__main__.py` wires
  this for every ECR repo it creates.
- **CloudFront caches the FE at the edge** for ~24h. After
  `make up STACK=frontend`, run `make fe-invalidate` to flush.
- **`ingest-jobs` queue has `visibility_timeout_seconds=3600`**
  (vs 60s for the other queues) because `data_ingestion`'s Lambda
  timeout is 600s and AWS requires queue visibility ≥ function
  timeout.
- **`make state-init` and `make destroy-all` are gated on a typed
  confirmation** (`destroy` for the latter) so you can't trigger them
  by accident.

## Tearing down

```bash
make destroy-all     # reverse-order destroy of every stack except _bootstrap
# Leave _bootstrap up unless you really mean to wipe the state bucket
# — destroying it orphans every other stack's state record.
```

If you do want to nuke `_bootstrap` too:

```bash
make destroy STACK=_bootstrap     # destroys the state bucket + lock table
                                  # Pulumi will lose track of any remaining
                                  # state references in there
```
