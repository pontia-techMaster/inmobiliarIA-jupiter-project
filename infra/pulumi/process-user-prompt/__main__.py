"""Lambda + SQS event source mapping for ``process_user_prompt``.

Builds the container image from ``services/process_user_prompt/Dockerfile.lambda``
(repo root as build context so the workspace + shared/ are visible),
pushes it to the ECR repo created by the platform stack, then deploys
a Lambda that consumes from the ``search-requests`` queue.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws
import pulumi_docker_build as docker_build

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402
from _shared.refs import PlatformRef  # noqa: E402

SERVICE = "process_user_prompt"

config = pulumi.Config()
memory_mb = config.require_int("lambda_memory_mb")
timeout_seconds = config.require_int("lambda_timeout_seconds")
batch_size = config.require_int("batch_size")

platform = PlatformRef()
repo_url = platform.ecr_repo_url(SERVICE)
log_group_name = platform.log_group_name(SERVICE)
search_requests_arn = platform.queue_arn("search-requests")
search_requests_url = platform.queue_url("search-requests")
query_jobs_arn = platform.queue_arn("query-jobs")
query_jobs_url = platform.queue_url("query-jobs")
ssm_gemini_arn = platform.ssm_gemini_api_key_arn()
ssm_gemini_name = platform.ssm_gemini_api_key_name()

repo_root = Path(__file__).resolve().parents[3]

# ── Build + push the Lambda container image ───────────────────────────────────
ecr_auth = aws.ecr.get_authorization_token_output()

image = docker_build.Image(
    "lambda-image",
    context=docker_build.BuildContextArgs(location=str(repo_root)),
    dockerfile=docker_build.DockerfileArgs(
        location=str(repo_root / "services" / SERVICE / "Dockerfile.lambda"),
    ),
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    tags=[repo_url.apply(lambda url: f"{url}:latest")],
    registries=[
        docker_build.RegistryArgs(
            address=repo_url,
            username=ecr_auth.user_name,
            password=ecr_auth.password,
        )
    ],
)

# ── IAM role for the Lambda ───────────────────────────────────────────────────
lambda_role = aws.iam.Role(
    "lambda-role",
    name=name(f"{SERVICE.replace('_', '-')}-lambda-role"),
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags=default_tags(),
)

# Permissions:
#   - logs:* on the prefixed CloudWatch log group
#   - sqs:Receive/Delete/GetAttrs on search-requests (event source needs these)
#   - sqs:SendMessage on query-jobs (handler publishes the next stage)
#   - ssm:GetParameter on the Gemini key
aws.iam.RolePolicy(
    "lambda-role-policy",
    role=lambda_role.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                    ],
                    "Resource": search_requests_arn,
                },
                {
                    "Effect": "Allow",
                    "Action": ["sqs:SendMessage"],
                    "Resource": query_jobs_arn,
                },
                {
                    # GetQueueUrl is needed by shared.sqs._queue_url to resolve
                    # the URL from a queue name at runtime. Account-scoped
                    # because ListQueues / GetQueueUrl don't accept ARNs.
                    "Effect": "Allow",
                    "Action": ["sqs:GetQueueUrl"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                    "Resource": ssm_gemini_arn,
                },
            ],
        }
    ),
)

# ── Lambda function ───────────────────────────────────────────────────────────
fn = aws.lambda_.Function(
    "lambda",
    name=name(SERVICE.replace("_", "-")),
    package_type="Image",
    image_uri=image.ref,  # digest-pinned reference returned by docker-build
    role=lambda_role.arn,
    memory_size=memory_mb,
    timeout=timeout_seconds,
    architectures=["x86_64"],
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            # Empty SQS_ENDPOINT_URL → shared.sqs._client() falls through to
            # boto3 defaults (regional endpoint + IAM role creds).
            "SQS_ENDPOINT_URL": "",
            # Override the queue NAME so settings.queue_query_jobs resolves
            # to the cloud-prefixed name (`inmo-dev-queue-query-jobs`).
            # shared.sqs.GetQueueUrl turns that into a full SQS URL.
            "QUEUE_QUERY_JOBS": query_jobs_url.apply(lambda u: u.split("/")[-1]),
            "GEMINI_API_KEY_PARAM": ssm_gemini_name,
        },
    ),
    logging_config=aws.lambda_.FunctionLoggingConfigArgs(
        log_format="Text",
        log_group=log_group_name,
    ),
    tags=default_tags(),
)

# ── SQS → Lambda event source mapping ────────────────────────────────────────
aws.lambda_.EventSourceMapping(
    "search-requests-trigger",
    event_source_arn=search_requests_arn,
    function_name=fn.name,
    batch_size=batch_size,
    function_response_types=["ReportBatchItemFailures"],
)

pulumi.export("function_arn", fn.arn)
pulumi.export("function_name", fn.name)
pulumi.export("image_ref", image.ref)
