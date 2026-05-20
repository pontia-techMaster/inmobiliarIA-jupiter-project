"""IAM OIDC provider + role for GitHub Actions.

Creates one OIDC provider (per AWS account) and a role whose trust
policy is scoped to specific git refs in a specific GitHub repo. The
role grants AdministratorAccess in dev — fine for a learning project,
but you'll want to narrow this before going to prod.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402

config = pulumi.Config()
repo: str = config.require("repo")
# Comma-separated list of refs (e.g., "refs/heads/main,refs/heads/release").
allowed_refs: list[str] = [r.strip() for r in config.require("allowed_refs").split(",") if r.strip()]
# If the account already has the GitHub OIDC provider (limit is 1 per account
# per URL), set this config and we'll reuse it instead of creating a new one.
existing_provider_arn: str | None = config.get("existing_provider_arn")

# GitHub's OIDC issuer + audience are constants — see
# https://docs.github.com/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
OIDC_URL = "https://token.actions.githubusercontent.com"
OIDC_AUDIENCE = "sts.amazonaws.com"
# GitHub rotates these — keep the list short and update if AWS starts
# rejecting tokens. (AWS no longer requires accurate thumbprints for the
# well-known GitHub issuer, but the field is still mandatory.)
OIDC_THUMBPRINTS = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

# ── OIDC provider (singleton per AWS account) ────────────────────────────────
# Each AWS account can only have one OIDC provider per issuer URL. On a fresh
# account we create it; on an account where another project already created
# it, set `existing_provider_arn` in config and we reuse the ARN.
provider_arn: pulumi.Output[str]
if existing_provider_arn:
    provider_arn = pulumi.Output.from_input(existing_provider_arn)
else:
    provider = aws.iam.OpenIdConnectProvider(
        "github-oidc-provider",
        url=OIDC_URL,
        client_id_lists=[OIDC_AUDIENCE],
        thumbprint_lists=OIDC_THUMBPRINTS,
        tags=default_tags(),
    )
    provider_arn = provider.arn


def _trust_policy(provider_arn: str) -> str:
    import json

    subs = [f"repo:{repo}:ref:{r}" for r in allowed_refs]
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Federated": provider_arn},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            f"{OIDC_URL.replace('https://', '')}:aud": OIDC_AUDIENCE,
                        },
                        "StringLike": {
                            f"{OIDC_URL.replace('https://', '')}:sub": subs,
                        },
                    },
                }
            ],
        }
    )


role = aws.iam.Role(
    "github-actions-role",
    name=name("github-actions-deploy"),
    assume_role_policy=provider_arn.apply(_trust_policy),
    description=f"Assumed by GitHub Actions workflows in {repo} to run Pulumi deploys.",
    max_session_duration=3600,
    tags=default_tags(),
)

# AdministratorAccess is fine for a single-user dev account. For prod,
# narrow this to the per-service permissions Pulumi actually exercises
# (IAM, Lambda, SQS, S3, DynamoDB, CloudFront, ECR, SSM, APIGateway).
aws.iam.RolePolicyAttachment(
    "github-actions-admin",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AdministratorAccess",
)

pulumi.export("provider_arn", provider_arn)
pulumi.export("role_arn", role.arn)
pulumi.export("role_name", role.name)
