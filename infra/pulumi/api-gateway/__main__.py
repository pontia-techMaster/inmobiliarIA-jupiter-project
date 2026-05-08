"""HTTP API → SQS service integration.

Flow:
    POST /search  { "request_id": "...", "prompt": "..." }
        ↓ API Gateway service integration (SQS-SendMessage)
    SQS:search-requests   body = the request body verbatim
        ↓ event source mapping
    Lambda: process_user_prompt

The frontend mints ``request_id`` (a UUID) before calling — API Gateway
HTTP API doesn't have request transformation rich enough to inject one
server-side, and we want to return it to the FE immediately for the
"Su petición está siendo procesada" UX.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402
from _shared.refs import PlatformRef  # noqa: E402

config = pulumi.Config()
cors_allow_origins: list[str] = config.require_object("cors_allow_origins")

platform = PlatformRef()
search_requests_url = platform.queue_url("search-requests")
search_requests_arn = platform.queue_arn("search-requests")

# ── IAM role API Gateway assumes when calling SQS ─────────────────────────────
apigw_role = aws.iam.Role(
    "apigw-sqs-role",
    name=name("apigw-sqs-role"),
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "apigateway.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags=default_tags(),
)

aws.iam.RolePolicy(
    "apigw-sqs-send-policy",
    role=apigw_role.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["sqs:SendMessage"],
                    "Resource": search_requests_arn,
                }
            ],
        }
    ),
)

# ── HTTP API ──────────────────────────────────────────────────────────────────
api = aws.apigatewayv2.Api(
    "http-api",
    name=name("http-api"),
    protocol_type="HTTP",
    cors_configuration=aws.apigatewayv2.ApiCorsConfigurationArgs(
        allow_origins=cors_allow_origins,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["content-type"],
        max_age=86400,
    ),
    tags=default_tags(),
)

# Service integration: SQS-SendMessage. Body of the HTTP request becomes
# the SQS message body verbatim.
sqs_integration = aws.apigatewayv2.Integration(
    "sqs-send-message",
    api_id=api.id,
    integration_type="AWS_PROXY",
    integration_subtype="SQS-SendMessage",
    credentials_arn=apigw_role.arn,
    payload_format_version="1.0",
    request_parameters={
        "QueueUrl": search_requests_url,
        "MessageBody": "$request.body",
    },
)

aws.apigatewayv2.Route(
    "post-search",
    api_id=api.id,
    route_key="POST /search",
    target=sqs_integration.id.apply(lambda iid: f"integrations/{iid}"),
)

stage = aws.apigatewayv2.Stage(
    "default-stage",
    api_id=api.id,
    name="$default",
    auto_deploy=True,
    tags=default_tags(),
)

pulumi.export("endpoint", stage.invoke_url)
pulumi.export("api_id", api.id)
