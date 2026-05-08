"""Lambda + SQS event source mapping + EventBridge schedule for
``data_ingestion``.

Differences vs the other service stacks:
  - No downstream queue (this service is a sink — writes to Qdrant).
  - EventBridge rule fires on a cron, publishes to ingest-jobs.
  - Lambda role gets s3:GetObject + s3:ListBucket on the HTML source.
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

SERVICE = "data_ingestion"
SERVICE_DASH = SERVICE.replace("_", "-")

config = pulumi.Config()
memory_mb = config.require_int("lambda_memory_mb")
timeout_seconds = config.require_int("lambda_timeout_seconds")
batch_size = config.require_int("batch_size")
schedule_expression = config.require("schedule_expression")
s3_prefix = config.require("s3_prefix")

platform = PlatformRef()
repo_url = platform.ecr_repo_url(SERVICE)
log_group_name = platform.log_group_name(SERVICE)
log_group_arn = platform.log_group_arn(SERVICE)

input_queue_arn = platform.queue_arn("ingest-jobs")
input_queue_url = platform.queue_url("ingest-jobs")

ssm_gemini_arn = platform.ssm_gemini_api_key_arn()
ssm_gemini_name = platform.ssm_gemini_api_key_name()
ssm_qdrant_arn = platform.ssm_qdrant_api_key_arn()
ssm_qdrant_name = platform.ssm_qdrant_api_key_name()
qdrant_url = platform.qdrant_url()

html_bucket_name = platform.html_bucket_name()
html_bucket_arn = platform.html_bucket_arn()

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
                    "Action": ["sqs:GetQueueUrl"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                    "Resource": [ssm_gemini_arn, ssm_qdrant_arn],
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": html_bucket_arn,
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": html_bucket_arn.apply(lambda arn: f"{arn}/*"),
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
    "ingest-jobs-trigger",
    event_source_arn=input_queue_arn,
    function_name=fn.name,
    batch_size=batch_size,
    function_response_types=["ReportBatchItemFailures"],
)

# ── EventBridge schedule → publish IngestJob to ingest-jobs ──────────────────
schedule_rule = aws.cloudwatch.EventRule(
    "ingest-schedule",
    name=name("ingest-schedule"),
    description="Periodic data_ingestion trigger",
    schedule_expression=schedule_expression,
    tags=default_tags(),
)

# Role EventBridge assumes to call sqs:SendMessage.
eb_role = aws.iam.Role(
    "eb-sqs-role",
    name=name(f"{SERVICE_DASH}-eb-sqs-role"),
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags=default_tags(),
)
aws.iam.RolePolicy(
    "eb-sqs-policy",
    role=eb_role.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["sqs:SendMessage"],
                    "Resource": input_queue_arn,
                }
            ],
        }
    ),
)

# Body is a literal JSON IngestJob with an s3:// source — the Lambda
# parses it, syncs to /tmp, then calls handle().
ingest_job_body = html_bucket_name.apply(
    lambda b: f'{{"source":"s3://{b}/{s3_prefix}"}}'
)

aws.cloudwatch.EventTarget(
    "ingest-schedule-target",
    rule=schedule_rule.name,
    arn=input_queue_arn,
    role_arn=eb_role.arn,
    input=ingest_job_body,
)

pulumi.export("function_arn", fn.arn)
pulumi.export("function_name", fn.name)
pulumi.export("image_ref", image.ref)
pulumi.export("schedule_rule_name", schedule_rule.name)
