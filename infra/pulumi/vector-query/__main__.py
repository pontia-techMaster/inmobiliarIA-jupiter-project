"""Lambda + SQS event source mapping for ``vector_query``.

Builds the container image from
``services/vector_query/Dockerfile.lambda`` (repo root as build context),
pushes to the ECR repo created by the platform stack, then deploys a
Lambda that consumes from ``query-jobs`` and publishes to ``rank-jobs``.
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

SERVICE = "vector_query"
SERVICE_DASH = SERVICE.replace("_", "-")

config = pulumi.Config()
memory_mb = config.require_int("lambda_memory_mb")
timeout_seconds = config.require_int("lambda_timeout_seconds")
batch_size = config.require_int("batch_size")

platform = PlatformRef()
repo_url = platform.ecr_repo_url(SERVICE)
log_group_name = platform.log_group_name(SERVICE)
log_group_arn = platform.log_group_arn(SERVICE)

input_queue_arn = platform.queue_arn("query-jobs")
input_queue_url = platform.queue_url("query-jobs")
output_queue_arn = platform.queue_arn("rank-jobs")
output_queue_url = platform.queue_url("rank-jobs")

ssm_gemini_arn = platform.ssm_gemini_api_key_arn()
ssm_gemini_name = platform.ssm_gemini_api_key_name()
ssm_qdrant_arn = platform.ssm_qdrant_api_key_arn()
ssm_qdrant_name = platform.ssm_qdrant_api_key_name()
qdrant_url = platform.qdrant_url()

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
    name=name(f"{SERVICE_DASH}-lambda-role"),
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

aws.iam.RolePolicy(
    "lambda-role-policy",
    role=lambda_role.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": [
                        log_group_arn,
                        log_group_arn.apply(lambda a: f"{a}:*"),
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                    ],
                    "Resource": input_queue_arn,
                },
                {
                    "Effect": "Allow",
                    "Action": ["sqs:SendMessage"],
                    "Resource": output_queue_arn,
                },
                {
                    # Needed by shared.sqs._queue_url to resolve names at runtime.
                    "Effect": "Allow",
                    "Action": ["sqs:GetQueueUrl"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                    "Resource": [ssm_gemini_arn, ssm_qdrant_arn],
                },
            ],
        }
    ),
)

# ── Lambda function ───────────────────────────────────────────────────────────
fn = aws.lambda_.Function(
    "lambda",
    name=name(SERVICE_DASH),
    package_type="Image",
    image_uri=image.ref,
    role=lambda_role.arn,
    memory_size=memory_mb,
    timeout=timeout_seconds,
    architectures=["x86_64"],
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "SQS_ENDPOINT_URL": "",
            "QUEUE_RANK_JOBS": output_queue_url.apply(lambda u: u.split("/")[-1]),
            "GEMINI_API_KEY_PARAM": ssm_gemini_name,
            "QDRANT_API_KEY_PARAM": ssm_qdrant_name,
            "QDRANT_URL": qdrant_url,
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
    "query-jobs-trigger",
    event_source_arn=input_queue_arn,
    function_name=fn.name,
    batch_size=batch_size,
    function_response_types=["ReportBatchItemFailures"],
)

pulumi.export("function_arn", fn.arn)
pulumi.export("function_name", fn.name)
pulumi.export("image_ref", image.ref)
