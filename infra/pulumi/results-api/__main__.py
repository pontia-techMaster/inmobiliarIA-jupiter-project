"""Zip-packaged Lambda + read-only HTTP routes on the existing API.

Adds two routes that share one Lambda + one integration:

  GET /results/{request_id}     — short-lived single-search lookup (TTL'd)
  GET /users/{user_id}/searches — durable per-user history

No Docker image, no service tree — handler.py only needs boto3, provided
by the Lambda runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402
from _shared.refs import ApiGatewayRef, PlatformRef  # noqa: E402

config = pulumi.Config()
memory_mb = config.require_int("lambda_memory_mb")
timeout_seconds = config.require_int("lambda_timeout_seconds")

platform = PlatformRef()
api = ApiGatewayRef()

results_table_name = platform.search_results_table_name()
results_table_arn = platform.search_results_table_arn()
user_searches_table_name = platform.user_searches_table_name()
user_searches_table_arn = platform.user_searches_table_arn()
api_id = api._r.require_output("api_id")  # raw output; ApiGatewayRef wraps endpoint only

region = aws.config.region or "eu-west-1"
account_id = aws.get_caller_identity().account_id

# ── Log group ─────────────────────────────────────────────────────────────────
log_group = aws.cloudwatch.LogGroup(
    "log-group",
    name=f"/aws/lambda/{name('results-api')}",
    retention_in_days=14,
    tags=default_tags(),
)

# ── IAM role for the Lambda ───────────────────────────────────────────────────
lambda_role = aws.iam.Role(
    "lambda-role",
    name=name("results-api-lambda-role"),
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
                        log_group.arn,
                        log_group.arn.apply(lambda a: f"{a}:*"),
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["dynamodb:GetItem"],
                    "Resource": results_table_arn,
                },
                {
                    "Effect": "Allow",
                    "Action": ["dynamodb:Query"],
                    # Querying an LSI requires permissions on both the table
                    # and the index ARN.
                    "Resource": [
                        user_searches_table_arn,
                        user_searches_table_arn.apply(lambda a: f"{a}/index/*"),
                    ],
                },
            ],
        }
    ),
)

# ── Lambda (zip from handler.py in this directory) ────────────────────────────
fn = aws.lambda_.Function(
    "lambda",
    name=name("results-api"),
    runtime="python3.12",
    handler="handler.handler",
    role=lambda_role.arn,
    memory_size=memory_mb,
    timeout=timeout_seconds,
    architectures=["x86_64"],
    code=pulumi.AssetArchive(
        {
            "handler.py": pulumi.FileAsset(str(Path(__file__).parent / "handler.py")),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "SEARCH_RESULTS_TABLE": results_table_name,
            "USER_SEARCHES_TABLE": user_searches_table_name,
        },
    ),
    logging_config=aws.lambda_.FunctionLoggingConfigArgs(
        log_format="Text",
        log_group=log_group.name,
    ),
    tags=default_tags(),
)

# ── Wire to the existing HTTP API ─────────────────────────────────────────────
# Two GET routes share one AWS_PROXY integration. CORS is inherited from
# the API-level config in the api-gateway stack.

# Broad invoke permission: any GET on this API can target the Lambda. We
# scope per-route via the routes themselves rather than splitting permissions.
aws.lambda_.Permission(
    "apigw-invoke-permission",
    action="lambda:InvokeFunction",
    function=fn.name,
    principal="apigateway.amazonaws.com",
    source_arn=api_id.apply(lambda i: f"arn:aws:execute-api:{region}:{account_id}:{i}/*/GET/*"),
)

integration = aws.apigatewayv2.Integration(
    "lambda-integration",
    api_id=api_id,
    integration_type="AWS_PROXY",
    integration_uri=fn.invoke_arn,
    payload_format_version="2.0",
)

aws.apigatewayv2.Route(
    "get-results",
    api_id=api_id,
    route_key="GET /results/{request_id}",
    target=integration.id.apply(lambda iid: f"integrations/{iid}"),
)

aws.apigatewayv2.Route(
    "get-user-searches",
    api_id=api_id,
    route_key="GET /users/{user_id}/searches",
    target=integration.id.apply(lambda iid: f"integrations/{iid}"),
)

pulumi.export("function_arn", fn.arn)
pulumi.export("function_name", fn.name)
