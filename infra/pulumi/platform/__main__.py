"""Platform foundation: queues, registries, secrets, log groups, data stores.

Service stacks (process-user-prompt, vector-query, …) read these as
StackReferences. Add a service to ``platform:services`` config and re-run
``pulumi up`` to provision its ECR repo + log group.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402

config = pulumi.Config()
services: list[str] = config.require_object("services")
qdrant_url_value: str = config.get("qdrant_url") or ""

# S3 bucket names are globally unique — same prefix-with-account-id pattern
# we use for the Pulumi state bucket.
account_id = aws.get_caller_identity().account_id

# ── SQS queues ────────────────────────────────────────────────────────────────
# Names match shared/settings.py so the same code talks to either ElasticMQ
# (local) or real SQS (cloud) by switching the endpoint.
QUEUES = [
    "search-requests",
    "query-jobs",
    "rank-jobs",
    "search-responses",
    "ingest-jobs",
]

queues: dict[str, aws.sqs.Queue] = {}
for q in QUEUES:
    queue = aws.sqs.Queue(
        f"queue-{q}",
        name=name(f"queue-{q}"),
        visibility_timeout_seconds=60,
        message_retention_seconds=345600,  # 4 days
        tags=default_tags(),
    )
    queues[q] = queue
    pulumi.export(f"queue_{q}_url", queue.url)
    pulumi.export(f"queue_{q}_arn", queue.arn)

# ── ECR repos (one per Lambda service) ────────────────────────────────────────
for svc in services:
    repo = aws.ecr.Repository(
        f"ecr-{svc}",
        name=name(f"ecr-{svc.replace('_', '-')}"),
        image_tag_mutability="MUTABLE",
        force_delete=True,  # dev convenience; flip for prod
        tags=default_tags(),
    )
    aws.ecr.LifecyclePolicy(
        f"ecr-{svc}-lifecycle",
        repository=repo.name,
        policy=pulumi.Output.json_dumps(
            {
                "rules": [
                    {
                        "rulePriority": 1,
                        "description": "Keep last 10 images",
                        "selection": {
                            "tagStatus": "any",
                            "countType": "imageCountMoreThan",
                            "countNumber": 10,
                        },
                        "action": {"type": "expire"},
                    }
                ]
            }
        ),
    )
    pulumi.export(f"ecr_{svc}_repo_url", repo.repository_url)
    pulumi.export(f"ecr_{svc}_repo_arn", repo.arn)

# ── CloudWatch log groups (one per Lambda service) ────────────────────────────
for svc in services:
    lg = aws.cloudwatch.LogGroup(
        f"log-group-{svc}",
        name=f"/aws/lambda/{name(svc.replace('_', '-'))}",
        retention_in_days=14,
        tags=default_tags(),
    )
    pulumi.export(f"log_group_{svc}_name", lg.name)
    pulumi.export(f"log_group_{svc}_arn", lg.arn)

# ── SSM Parameter Store ───────────────────────────────────────────────────────
# Created with placeholder values. Set the real keys out-of-band:
#   aws ssm put-parameter --name <name> --type SecureString --value '...' --overwrite
# We `ignore_changes=["value"]` so subsequent `pulumi up` doesn't reset them.

gemini_key = aws.ssm.Parameter(
    "ssm-gemini-api-key",
    name=name("gemini-api-key"),
    type="SecureString",
    value="REPLACE_ME",
    description="Google Gemini API key consumed by Lambda services",
    tags=default_tags(),
    opts=pulumi.ResourceOptions(ignore_changes=["value"]),
)
pulumi.export("ssm_gemini_api_key_arn", gemini_key.arn)
pulumi.export("ssm_gemini_api_key_name", gemini_key.name)

qdrant_api_key = aws.ssm.Parameter(
    "ssm-qdrant-api-key",
    name=name("qdrant-api-key"),
    type="SecureString",
    value="REPLACE_ME",
    description="Qdrant Cloud API key consumed by vector_query, ranking_and_rendering, data_ingestion",
    tags=default_tags(),
    opts=pulumi.ResourceOptions(ignore_changes=["value"]),
)
pulumi.export("ssm_qdrant_api_key_arn", qdrant_api_key.arn)
pulumi.export("ssm_qdrant_api_key_name", qdrant_api_key.name)

# Qdrant URL is non-sensitive — exported directly so service stacks can pass
# it as a plain Lambda env var. Set this in Pulumi.dev.yaml after Qdrant
# Cloud signup.
pulumi.export("qdrant_url", qdrant_url_value)

# ── S3 source bucket (HTML for ingestion) ─────────────────────────────────────
html_bucket = aws.s3.BucketV2(
    "html-source-bucket",
    bucket=name(f"html-source-{account_id}"),
    force_destroy=True,
    tags=default_tags(),
)
aws.s3.BucketPublicAccessBlock(
    "html-source-bucket-public-access",
    bucket=html_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)
pulumi.export("html_bucket_name", html_bucket.bucket)
pulumi.export("html_bucket_arn", html_bucket.arn)

# ── DynamoDB user-data table (for future user-data microservice) ──────────────
users_table = aws.dynamodb.Table(
    "users-table",
    name=name("users"),
    billing_mode="PAY_PER_REQUEST",
    hash_key="user_id",
    attributes=[aws.dynamodb.TableAttributeArgs(name="user_id", type="S")],
    tags=default_tags(),
)
pulumi.export("users_table_name", users_table.name)
pulumi.export("users_table_arn", users_table.arn)
