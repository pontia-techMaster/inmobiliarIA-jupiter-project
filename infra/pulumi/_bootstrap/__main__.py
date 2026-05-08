"""Remote state backend for every other stack.

Creates:
  - S3 bucket with versioning + AES256 + public-access block (state lives here)
  - DynamoDB table for Pulumi's locking (prevents concurrent writes)

This stack is the only one that uses the LOCAL backend. After it's up,
point the Pulumi CLI at the bucket and re-run every other stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402

# S3 bucket names are globally unique across all AWS accounts, so the
# project prefix alone isn't enough — include the account id.
account_id = aws.get_caller_identity().account_id

state_bucket = aws.s3.BucketV2(
    "state-bucket",
    bucket=name(f"pulumi-state-{account_id}"),
    tags=default_tags(),
)

aws.s3.BucketVersioningV2(
    "state-bucket-versioning",
    bucket=state_bucket.id,
    versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
        status="Enabled",
    ),
)

aws.s3.BucketServerSideEncryptionConfigurationV2(
    "state-bucket-encryption",
    bucket=state_bucket.id,
    rules=[
        aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
            apply_server_side_encryption_by_default=(
                aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256",
                )
            ),
        )
    ],
)

aws.s3.BucketPublicAccessBlock(
    "state-bucket-public-access",
    bucket=state_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

lock_table = aws.dynamodb.Table(
    "state-lock-table",
    name=name("pulumi-state-lock"),
    billing_mode="PAY_PER_REQUEST",
    hash_key="LockID",
    attributes=[aws.dynamodb.TableAttributeArgs(name="LockID", type="S")],
    tags=default_tags(),
)

pulumi.export("state_bucket", state_bucket.bucket)
pulumi.export("state_lock_table", lock_table.name)
pulumi.export("region", aws.config.region)
