"""Lambda + SQS event source mapping for ``ranking_and_rendering``.

Consumes ``rank-jobs``, queries Qdrant Cloud for full payloads, reranks,
publishes ``SearchResponse`` to ``search-responses``.
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

SERVICE = "ranking_and_rendering"
SERVICE_DASH = SERVICE.replace("_", "-")

config = pulumi.Config()
memory_mb = config.require_int("lambda_memory_mb")
timeout_seconds = config.require_int("lambda_timeout_seconds")
batch_size = config.require_int("batch_size")

platform = PlatformRef()
repo_url = platform.ecr_repo_url(SERVICE)
log_group_name = platform.log_group_name(SERVICE)
log_group_arn = platform.log_group_arn(SERVICE)

input_queue_arn = platform.queue_arn("rank-jobs")
output_queue_arn = platform.queue_arn("search-responses")
output_queue_url = platform.queue_url("search-responses")

ssm_qdrant_arn = platform.ssm_qdrant_api_key_arn()
ssm_qdrant_name = platform.ssm_qdrant_api_key_name()
qdrant_url = platform.qdrant_url()

repo_root = Path(__file__).resolve().parents[3]

ecr_auth = aws.ecr.get_authorization_token_output()

image = docker_build.Image(
    "lambda-image",
    context=docker_build.BuildContextArgs(location=str(repo_root)),
    dockerfile=docker_build.DockerfileArgs(
        location=str(repo_root / "services" / SERVICE / "Dockerfile.lambda"),
    ),
    platforms=[docker_build.Platform.LINUX_AMD64],
    # `push=False` avoids Pulumi auto-adding a second export; the actual
    # registry push happens via `push=true` in the export raw spec.
    push=False,
    tags=[repo_url.apply(lambda url: f"{url}:latest")],
    # Lambda only accepts plain image manifests, not OCI image indexes
    # with attestations. Disable provenance + SBOM via a raw buildx
    # output spec.
    exports=[
        docker_build.ExportArgs(
            raw="type=registry,push=true,provenance=false,sbom=false",
        )
    ],
    registries=[
        docker_build.RegistryArgs(
            address=repo_url,
            username=ecr_auth.user_name,
            password=ecr_auth.password,
        )
    ],
)

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
                    "Effect": "Allow",
                    "Action": ["sqs:GetQueueUrl"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                    "Resource": ssm_qdrant_arn,
                },
            ],
        }
    ),
)

fn = aws.lambda_.Function(
    "lambda",
    name=name(SERVICE_DASH),
    package_type="Image",
    image_uri=pulumi.Output.all(repo_url, image.digest).apply(lambda a: f"{a[0]}@{a[1]}"),
    role=lambda_role.arn,
    memory_size=memory_mb,
    timeout=timeout_seconds,
    architectures=["x86_64"],
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "SQS_ENDPOINT_URL": "",
            "QUEUE_SEARCH_RESPONSES": output_queue_url.apply(lambda u: u.split("/")[-1]),
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

aws.lambda_.EventSourceMapping(
    "rank-jobs-trigger",
    event_source_arn=input_queue_arn,
    function_name=fn.name,
    batch_size=batch_size,
    function_response_types=["ReportBatchItemFailures"],
)

pulumi.export("function_arn", fn.arn)
pulumi.export("function_name", fn.name)
pulumi.export("image_ref", image.ref)
