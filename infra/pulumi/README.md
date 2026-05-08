# Pulumi microstacks — InmobiliarIA Júpiter

See [`docs/architecture2.md`](../../docs/architecture2.md) for the cloud
topology this provisions.

## Layout

```
.
├── pyproject.toml         shared deps for every stack (one venv)
├── Makefile               wraps `pulumi up/preview/destroy` per stack
├── _shared/               python helpers: naming, tags, stack refs
├── _bootstrap/            state backend (LOCAL → S3 migration, one-time)
├── platform/              SQS, ECR, SSM, CloudWatch
├── api-gateway/           HTTP API + SQS service integration
├── frontend/              S3 + CloudFront
├── process-user-prompt/   Lambda + SQS event source mapping
├── vector-query/          (later)
├── ranking-and-rendering/ (later)
└── data-ingestion/        (later)
```

## Prerequisites

- **AWS CLI** with a profile named **`inmo`** pointing at the deploy
  account. Every `Pulumi.dev.yaml` pins `aws:profile: inmo` so Pulumi
  uses these creds regardless of `AWS_PROFILE` / default profile.

  ```bash
  aws configure --profile inmo
  # paste access key, secret, region (eu-west-1)
  aws --profile inmo sts get-caller-identity   # confirm the right account
  ```

  Each teammate runs that once with their own IAM user in the deploy
  account. Profile name is the contract; actual creds stay local.

- **Pulumi CLI**: `brew install pulumi/tap/pulumi`.
- **Docker daemon** running (the `process-user-prompt` stack builds a
  Lambda container image).
- **Node 20+** (the `frontend` stack runs `npm run build`).

For raw `aws` CLI commands documented below, prefix with
`--profile inmo` (or `export AWS_PROFILE=inmo` for the session).

## One-time setup

```bash
cd infra/pulumi

# 1. Create venv with Pulumi + plugins
make install

# 2. Initialize remote state — uses LOCAL backend (chicken-and-egg)
make state-init
# → outputs `state_bucket` and `state_lock_table`

# 3. Switch the CLI to use the S3 bucket as backend for everything else
export PULUMI_BACKEND_URL=s3://<state_bucket>?region=eu-west-1
make login-remote
```

After step 3 every `pulumi up` writes its state to S3 with a DDB lock.

## Day-one slice (FE → APIGW → process_user_prompt)

Deploy in this order — each stack reads outputs from the previous one:

```bash
make up STACK=platform              # SQS, ECR, SSM, log group

# Set the real Gemini key (SSM is created with a placeholder)
aws --profile inmo ssm put-parameter \
    --name inmo-dev-gemini-api-key \
    --type SecureString --value "<your real key>" --overwrite

make up STACK=api-gateway           # HTTP API, returns endpoint
make up STACK=process-user-prompt   # builds image, deploys Lambda
make up STACK=frontend              # builds React app, uploads to S3
```

Inspect outputs:

```bash
make outputs STACK=api-gateway
make outputs STACK=frontend
```

## Tearing it down

```bash
# reverse order
make destroy STACK=frontend
make destroy STACK=process-user-prompt
make destroy STACK=api-gateway
make destroy STACK=platform
# leave _bootstrap up unless you really mean it; destroying it deletes the
# state bucket and you'll lose track of every other stack's state.
```

## Stacks (deploy graph)

```
_bootstrap                       (S3 state bucket + DDB lock)
    │
platform                         (SQS, ECR, SSM, CloudWatch)
    ├── api-gateway              (HTTP API → SQS:search-requests)
    │       │
    │       └── frontend         (S3 + CloudFront, reads api endpoint)
    │
    └── process-user-prompt      (Lambda triggered by SQS:search-requests)
```

## Adding a new service stack

1. Copy `process-user-prompt/` to `<service>/`.
2. Edit `Pulumi.yaml` (project name, description).
3. Edit `__main__.py`:
   - Change `SERVICE` constant at the top.
   - Change the input queue (`platform.queue_arn("search-requests")`)
     to whatever this service consumes.
   - Update the IAM policy to scope SQS perms to the right queues.
4. Add a `Dockerfile.lambda` next to the service (see
   `services/process_user_prompt/Dockerfile.lambda` for the template).
5. Add a `lambda_handler.py` next to `worker.py` in the service src.
6. **Set the cloud env vars on the Lambda** — see
   [`docs/architecture2.md` § Service runtime config](../../docs/architecture2.md#service-runtime-config--local-vs-cloud)
   for the full table. At minimum:
   - `SQS_ENDPOINT_URL=""` so `shared/sqs.py` uses real SQS.
   - `QUEUE_<OUTPUT>=<actual-cloud-queue-name>` for every queue the
     service writes to.
7. Add the service to `platform/Pulumi.dev.yaml` `services:` list and
   re-run `make up STACK=platform` so the ECR repo + log group exist.
8. `make up STACK=<service>`.
